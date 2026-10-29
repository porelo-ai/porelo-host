"""Exercise root admission and revocation against an isolated filesystem and command recorder."""

import base64
import hashlib
import io
import json
import os
import runpy
import ssl
import stat
import struct
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "roles/porelo/files/porelo-host-person"


def ssh_key(number):
    kind = b"ssh-ed25519"
    blob = struct.pack(">I", len(kind)) + kind + struct.pack(">I", 32) + bytes([number]) * 32
    return "ssh-ed25519 " + base64.b64encode(blob).decode()


def wg_key(number):
    return base64.b64encode(bytes([number]) * 32).decode()


def laptop(name="laptop", number=1, address=""):
    return f"{name} {ssh_key(number)} {wg_key(number)}" + (f" {address}" if address else "") + "\n"


def snapshot(root):
    return {
        str(path.relative_to(root)): (
            stat.S_IMODE(path.lstat().st_mode),
            path.lstat().st_mtime_ns,
            path.read_bytes() if path.is_file() and not path.is_symlink() else None,
        )
        for path in root.rglob("*")
    }


class Host:
    def __init__(self, root, factory):
        self.root = root
        self.factory = factory
        self.calls = []
        self.events = []
        self.accounts = {"root": 0, "daemon": 1}
        self.groups = {"kvm", "libvirt"}
        self.commands = {
            "useradd",
            "usermod",
            "userdel",
            "loginctl",
            "groupadd",
            "wg",
            "runuser",
            "porelo",
            "systemctl",
        }
        self.euid = 0
        self.fail = None
        self.failed_output = ""
        self.inspect = lambda args: None
        self.hook_inspect = lambda name, values: None

    def path(self, name):
        return self.root / name.lstrip("/")

    def write(self, name, text, mode=0o600):
        path = self.path(name)
        for directory in reversed(path.parents):
            if self.root in directory.parents or directory == self.root:
                directory.mkdir(exist_ok=True, mode=0o700)
        path.write_text(text)
        path.chmod(mode)
        return path

    def run(self, args):
        self.calls.append(args)
        self.events.append(args)
        self.inspect(args)
        if self.fail and args[: len(self.fail)] == self.fail:
            return subprocess.CompletedProcess(args, 1, self.failed_output, self.failed_output)
        if args[0] == "useradd":
            self.accounts[args[-1]] = max(999, *self.accounts.values()) + 1
        if args[0] == "groupadd":
            self.groups.add(args[-1])
        if args[0] == "userdel":
            self.accounts.pop(args[-1], None)
        return subprocess.CompletedProcess(args, 0, "", "")

    def invoke(self, *args, data=None, sudo_user=None):
        def hook(name, values):
            self.hook_inspect(name, values)
            self.events.append([name, *values])

        hooks = {
            name: lambda *values, name=name: hook(name, values)
            for name in ("forge_admit", "matrix_issue", "forge_lock", "matrix_expel_revoke")
        }
        extra = {} if sudo_user is None else {"sudo_user": sudo_user}
        return self.factory(
            self.root,
            self.run,
            euid=self.euid,
            owner=os.getuid(),
            accounts=self.accounts,
            groups=self.groups,
            commands=self.commands,
            hooks=hooks,
            **extra,
        )(list(args), laptop().encode() if data is None else data)


@pytest.fixture
def host(tmp_path):
    namespace = runpy.run_path(str(SCRIPT), run_name="person_unit_tests")
    h = Host(tmp_path, namespace["_test_entry"])
    h.write("/etc/porelo-host/forge.conf", "address=10.73.7.1\n")
    h.write("/etc/porelo-host/vpn.conf", "admin_address=10.73.7.2\n")
    h.write("/etc/subuid", "existing:100000:65536\n", 0o644)
    h.write("/etc/subgid", "existing:200000:65536\n", 0o644)
    return h


def refused(host, capsys, code, *args, data=None, diagnostic=None, sudo_user=None):
    before = snapshot(host.root)
    host.calls.clear()
    host.events.clear()
    assert host.invoke(*args, data=data, sudo_user=sudo_user) == code
    output = capsys.readouterr()
    assert not output.out, "a refusal must never answer success"
    assert output.err.startswith("porelo-host-person: ")
    if diagnostic:
        assert diagnostic in output.err
    assert snapshot(host.root) == before, "refusal must leave every file, directory, mode and mtime alone"
    assert host.calls == [], "refusal must precede every system command"
    assert host.events == [], "refusal must precede external hooks"
    return output


@pytest.mark.parametrize(
    "args",
    [
        (),
        ("sync",),
        ("sync", "Alice"),
        ("sync", "-alpha"),
        ("sync", "alpha", "extra"),
        ("lock",),
        ("purge", "alice", "--force"),
        ("add", "alice"),
        ("add", "alice", "--role", "developer"),
        ("add", "alice", "--role", "project-admin", "extra"),
    ],
)
def test_wrong_calls_cannot_change_the_host(host, capsys, args):
    """Prevent unintended privileged operations through malformed arguments."""
    refused(host, capsys, 64, *args)


def test_non_root_is_refused_before_reading_configuration_or_input(host, capsys):
    """Prevent an unprivileged invocation from reaching records or any account operation."""
    host.euid = 1000
    host.path("/etc/porelo-host/forge.conf").unlink()
    refused(host, capsys, 69, "add", "alice", "--role", "project-admin", data=b"\xff", diagnostic="root")


@pytest.mark.parametrize(
    "user,code",
    [
        ("root", 65),
        ("daemon", 65),
        ("existing", 65),
        ("Alice", 64),
        ("-alice", 64),
        ("../alice", 64),
        ("a" * 32, 64),
        ("a\n", 64),
    ],
)
def test_account_names_cannot_take_over_an_existing_account(host, capsys, user, code):
    """Prevent overwriting root, system accounts, unrelated accounts or paths outside the people directory."""
    host.accounts["existing"] = 1000
    refused(host, capsys, code, "add", user, "--role", "project-admin")


def test_a_name_a_group_already_holds_is_no_new_persons(host, capsys):
    """Prevent a person from being refused half-way by useradd, or put into a system group such as Ubuntu's operator."""
    host.groups.add("operator")
    refused(host, capsys, 65, "add", "operator", "--role", "project-admin", diagnostic="group")


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"\xff",
        b"\n",
        laptop().encode() + b"\n",
        laptop().replace("laptop ", "bad_name ").encode(),
        laptop().replace("laptop ", "-bad ").encode(),
        laptop().replace("laptop ", "a" * 33 + " ").encode(),
        laptop().replace(" ", "  ", 1).encode(),
        laptop().replace(" ", "\t", 1).encode(),
        laptop().replace("\n", "\r\n").encode(),
        laptop().rstrip().encode() + b" comment\n",
        b"laptop ssh-rsa AAAA AAAA\n",
        laptop().replace(ssh_key(1), "ssh-ed25519 AAAA").encode(),
        laptop().replace(wg_key(1), "A" * 44).encode(),
        laptop().encode() + laptop("laptop", 2).encode(),
        laptop().encode() + laptop("second", 1).encode(),
        (laptop() + laptop("second", 2).replace(wg_key(2), wg_key(1))).encode(),
        (laptop() + laptop("second", 2).replace(ssh_key(2), ssh_key(1))).encode(),
        b"x" * 262145,
    ],
    ids=[
        "empty",
        "invalid-utf8",
        "empty-line",
        "extra-line",
        "bad-name",
        "leading-dash",
        "long-name",
        "double-space",
        "tab",
        "carriage-return",
        "comment",
        "wrong-ssh-kind",
        "bad-ssh-blob",
        "bad-vpn-key",
        "repeated-name",
        "repeated-keys",
        "repeated-vpn-key",
        "repeated-ssh-key",
        "oversized-block",
    ],
)
def test_bad_key_blocks_cannot_partially_admit_a_person(host, capsys, data):
    """Prevent malformed or repeated credentials from granting partial SSH or VPN access."""
    output = refused(host, capsys, 64, "add", "alice", "--role", "project-admin", data=data)
    assert ssh_key(1) not in output.err and wg_key(1) not in output.err


@pytest.mark.parametrize(
    "address,code",
    [
        ("10.73.8.3", 65),
        ("10.73.7.1", 65),
        ("10.73.7.2", 65),
        ("10.73.7.0", 65),
        ("10.73.7.255", 65),
        ("10.73.7.3/32", 64),
        ("::1", 64),
        ("10.73.7.999", 64),
    ],
)
def test_reserved_or_invalid_addresses_cannot_redirect_vpn_traffic(host, capsys, address, code):
    """Prevent stealing host/admin traffic or installing an invalid or out-of-network route."""
    refused(host, capsys, code, "add", "alice", "--role", "project-admin", data=laptop(address=address).encode())


@pytest.mark.parametrize(
    "file,change,code",
    [
        ("/etc/porelo-host/forge.conf", "missing", 69),
        ("/etc/porelo-host/forge.conf", "writable", 69),
        ("/etc/porelo-host/forge.conf", "link", 69),
        ("/etc/porelo-host/vpn.conf", "missing", 69),
        ("/etc/porelo-host/vpn.conf", "writable", 69),
        ("/etc/porelo-host", "writable", 69),
        ("/etc/ssh/authorized_keys/alice", "directory", 73),
        ("/etc/ssh/authorized_keys/alice", "link", 73),
        ("/etc/ssh/authorized_keys", "writable", 73),
        ("/etc/wireguard/porelo-host-peers/alice.conf", "directory", 73),
        ("/etc/porelo-host/people/alice.conf", "link", 69),
        ("/etc/subuid", "writable", 69),
        ("/etc/subgid", "missing", 69),
    ],
)
def test_untrusted_or_unwritable_paths_cannot_be_used_by_root(host, capsys, file, change, code):
    """Prevent symlink writes, untrusted configuration and late path refusal after account creation."""
    path = host.path(file)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if change == "missing":
        path.unlink()
    elif change == "writable":
        if not path.exists():
            path.mkdir(mode=0o700)
        path.chmod(0o777)
    elif change == "directory":
        path.mkdir()
    else:
        if path.exists():
            path.unlink()
        path.symlink_to(host.path("/etc/subuid"))
    refused(host, capsys, code, "add", "alice", "--role", "project-admin")


@pytest.mark.parametrize(
    "file,text",
    [
        ("forge.conf", "address=10.73.999.1\n"),
        ("forge.conf", "address=10.73.7.3\n"),
        ("forge.conf", "address=10.73.7.1\naddress=10.73.8.1\n"),
        ("vpn.conf", "key=/etc/wireguard/key\n"),
        ("vpn.conf", "admin_address=10.73.8.2\n"),
    ],
)
def test_bad_host_configuration_cannot_choose_the_network(host, capsys, file, text):
    """Prevent an ambiguous network or missing admin reservation from admitting a peer at the wrong address."""
    host.write("/etc/porelo-host/" + file, text)
    refused(host, capsys, 69, "add", "alice", "--role", "project-admin")


@pytest.mark.parametrize("command", ["useradd", "usermod", "loginctl", "groupadd", "wg"])
def test_missing_dependencies_cannot_leave_a_partial_account(host, capsys, command):
    """Prevent discovering a missing required program after access or an account has been created."""
    host.commands.remove(command)
    refused(host, capsys, 69, "add", "alice", "--role", "project-admin", diagnostic=command)


def test_add_orders_account_keys_peers_hooks_and_record(host, capsys):
    """Prevent recording successful admission before every required account and access step completed."""
    record = host.path("/etc/porelo-host/people/alice.conf")
    keys = host.path("/etc/ssh/authorized_keys/alice")
    peers = host.path("/etc/wireguard/porelo-host-peers/alice.conf")

    def inspect(args):
        assert not record.exists(), "the record must be published last"
        if args[0] == "wg":
            assert keys.read_text() == f'from="10.73.7.3" {ssh_key(1)}\nfrom="10.73.7.4" {ssh_key(2)}\n'
        else:
            assert not keys.exists() and not peers.exists()

    host.inspect = inspect

    def inspect_hook(name, values):
        assert not record.exists(), "the record must follow both admission hooks"
        assert peers.is_file(), "both hooks must follow persistent VPN admission"

    host.hook_inspect = inspect_hook
    assert host.invoke("add", "alice", "--role", "project-admin", data=(laptop() + laptop("second", 2)).encode()) == 0
    result = json.loads(capsys.readouterr().out)
    assert result == {
        "person": "alice",
        "role": "project-admin",
        "laptops": [
            {"laptop": "laptop", "vpn_address": "10.73.7.3"},
            {"laptop": "second", "vpn_address": "10.73.7.4"},
        ],
    }
    assert host.calls == [
        [
            "useradd",
            "--create-home",
            "--user-group",
            "--shell",
            "/bin/bash",
            "--key",
            "SUB_UID_COUNT=0",
            "--key",
            "SUB_GID_COUNT=0",
            "alice",
        ],
        ["loginctl", "enable-linger", "alice"],
        ["usermod", "--add-subuids", "165536-231071", "alice"],
        ["usermod", "--add-subgids", "265536-331071", "alice"],
        ["groupadd", "--system", "porelo-people"],
        ["usermod", "--append", "--groups", "kvm,libvirt,porelo-people", "alice"],
        ["wg", "set", "wg-porelo", "peer", wg_key(1), "allowed-ips", "10.73.7.3/32"],
        ["wg", "set", "wg-porelo", "peer", wg_key(2), "allowed-ips", "10.73.7.4/32"],
    ]
    assert [event[0] for event in host.events[-2:]] == ["forge_admit", "matrix_issue"]
    assert peers.read_text() == (
        f"[Peer]\nPublicKey = {wg_key(1)}\nAllowedIPs = 10.73.7.3/32\n\n"
        f"[Peer]\nPublicKey = {wg_key(2)}\nAllowedIPs = 10.73.7.4/32\n\n"
    )
    assert record.read_text() == (
        "member=hand\nlocked=false\n"
        f"laptop=laptop {ssh_key(1)} {wg_key(1)} 10.73.7.3\n"
        f"laptop=second {ssh_key(2)} {wg_key(2)} 10.73.7.4\n"
    )
    for path, mode in [
        (record, 0o600),
        (peers, 0o600),
        (keys, 0o644),
        (record.parent, 0o700),
        (peers.parent, 0o700),
        (keys.parent, 0o755),
    ]:
        assert stat.S_IMODE(path.stat().st_mode) == mode
        assert path.stat().st_uid == os.getuid()
    assert not list(host.root.rglob(".porelo-host-person.*")), "atomic writes must leave no staging files"


def test_rerun_preserves_files_addresses_and_answer(host, capsys):
    """Prevent repeated admission from allocating another address or re-enabling privileges."""
    data = (laptop("first", 1, "10.73.7.20") + laptop("second", 2)).encode()
    assert host.invoke("add", "alice", "--role", "project-admin", data=data) == 0
    first = capsys.readouterr().out
    before = snapshot(host.root)
    host.calls.clear()
    host.events.clear()
    rerun = (laptop("second", 2) + laptop("first", 1)).encode()
    assert host.invoke("add", "alice", "--role", "project-admin", data=rerun) == 0
    assert capsys.readouterr().out == first
    assert snapshot(host.root) == before
    assert host.calls == [] and host.events == []


@pytest.mark.parametrize(
    "data",
    [laptop(number=2), laptop(address="10.73.7.9"), laptop("renamed"), laptop() + laptop("extra", 2)],
    ids=["changed-keys", "changed-address", "renamed-laptop", "extra-laptop"],
)
def test_recorded_credentials_cannot_be_replaced(host, capsys, data):
    """Prevent add from silently substituting an admitted person's keys, laptops or address."""
    assert host.invoke("add", "alice", "--role", "project-admin") == 0
    capsys.readouterr()
    refused(host, capsys, 65, "add", "alice", "--role", "project-admin", data=data.encode())


@pytest.mark.parametrize(
    "data",
    [
        laptop("other", 2, "10.73.7.3"),
        laptop("other", 1),
        laptop("other", 2).replace(wg_key(2), wg_key(1)),
        laptop("other", 2).replace(ssh_key(2), ssh_key(1)),
    ],
    ids=["taken-address", "taken-keys", "taken-vpn-key", "taken-ssh-key"],
)
def test_other_people_cannot_steal_a_laptop_key_or_address(host, capsys, data):
    """Prevent a new person from taking another person's SSH identity or VPN route."""
    assert host.invoke("add", "alice", "--role", "project-admin") == 0
    capsys.readouterr()
    refused(host, capsys, 65, "add", "bob", "--role", "project-admin", data=data.encode())


def test_allocation_reserves_requested_addresses_before_automatic_ones(host, capsys):
    """Prevent automatic allocation from taking an address requested by a later laptop in the block."""
    data = (laptop() + laptop("second", 2, "10.73.7.3")).encode()
    assert host.invoke("add", "alice", "--role", "project-admin", data=data) == 0
    addresses = [item["vpn_address"] for item in json.loads(capsys.readouterr().out)["laptops"]]
    assert addresses == ["10.73.7.4", "10.73.7.3"]


def test_duplicate_requested_addresses_are_refused(host, capsys):
    """Prevent assigning the same VPN address to two peers within one admission."""
    refused(
        host,
        capsys,
        65,
        "add",
        "alice",
        "--role",
        "project-admin",
        data=(laptop(address="10.73.7.3") + laptop("second", 2, "10.73.7.3")).encode(),
    )


def test_lock_removes_access_before_stopping_tasks_and_is_idempotent(host, capsys):
    """Prevent a locked person from keeping SSH, VPN, sessions or a reusable enabled account."""
    assert host.invoke("add", "alice", "--role", "project-admin") == 0
    capsys.readouterr()
    host.calls.clear()
    host.events.clear()

    def inspect(args):
        assert not host.path("/etc/ssh/authorized_keys/alice").exists()
        assert not host.path("/etc/wireguard/porelo-host-peers/alice.conf").exists()

    host.inspect = inspect
    assert host.invoke("lock", "alice", data=b"") == 0
    assert json.loads(capsys.readouterr().out) == {"person": "alice", "locked": True}
    assert host.events == [
        ["wg", "set", "wg-porelo", "peer", wg_key(1), "remove"],
        ["forge_lock", "alice"],
        ["matrix_expel_revoke", "alice"],
        ["runuser", "-u", "alice", "--", "env", "XDG_RUNTIME_DIR=/run/user/1000", "porelo", "task", "stop", "--all"],
        ["loginctl", "terminate-user", "alice"],
        ["usermod", "--lock", "--expiredate", "1", "alice"],
    ]
    assert "locked=true\n" in host.path("/etc/porelo-host/people/alice.conf").read_text()
    before = snapshot(host.root)
    host.calls.clear()
    host.events.clear()
    assert host.invoke("lock", "alice", data=b"") == 0
    assert snapshot(host.root) == before and host.events == []
    capsys.readouterr()
    # Locked is not admitted: only purge and a new add give the person access again.
    refused(host, capsys, 65, "add", "alice", "--role", "project-admin", diagnostic="locked")


def test_failed_task_stop_is_reported_but_lock_continues_without_leaking_output(host, capsys):
    """Prevent a task failure or its untrusted output from retaining access or disclosing credentials."""
    assert host.invoke("add", "alice", "--role", "project-admin") == 0
    capsys.readouterr()
    host.fail = ["runuser"]
    host.failed_output = laptop() + "untrusted-token"
    assert host.invoke("lock", "alice", data=b"") == 0
    output = capsys.readouterr()
    assert "task stop" in output.err and "exit 1" in output.err
    assert "untrusted-token" not in output.err and ssh_key(1) not in output.err and wg_key(1) not in output.err
    assert "locked=true" in host.path("/etc/porelo-host/people/alice.conf").read_text()


def test_purge_locks_first_clears_vault_then_removes_account_and_ranges(host, capsys):
    """Prevent deleting an active account or abandoning its vault and subordinate IDs."""
    assert host.invoke("add", "alice", "--role", "project-admin") == 0
    host.write("/etc/subuid", "existing:100000:65536\nalice:165536:65536\nalice:400000:65536\n", 0o644)
    host.write("/etc/subgid", "existing:200000:65536\nalice:265536:65536\n", 0o644)
    host.calls.clear()
    capsys.readouterr()
    assert host.invoke("purge", "alice", data=b"") == 0
    assert json.loads(capsys.readouterr().out) == {"person": "alice", "purged": True}
    assert host.calls[-9:] == [
        ["usermod", "--lock", "--expiredate", "1", "alice"],
        # A locked account is expired, which PAM refuses to runuser and to the user manager; its password stays locked.
        ["usermod", "--expiredate", "", "alice"],
        ["systemctl", "start", "user@1000.service"],
        ["runuser", "-u", "alice", "--", "env", "XDG_RUNTIME_DIR=/run/user/1000", "porelo", "task", "stop", "--all"],
        [
            "runuser",
            "-u",
            "alice",
            "--",
            "env",
            "XDG_RUNTIME_DIR=/run/user/1000",
            "porelo",
            "vault",
            "clear",
            "--yes",
            "--force",
        ],
        ["loginctl", "disable-linger", "alice"],
        ["loginctl", "terminate-user", "alice"],
        # terminate-user returns before the manager ends; userdel refuses an account still running anything.
        ["systemctl", "stop", "user@1000.service"],
        ["userdel", "--remove", "alice"],
    ]
    assert not host.path("/etc/porelo-host/people/alice.conf").exists()
    assert host.path("/etc/subuid").read_text() == "existing:100000:65536\n"
    assert host.path("/etc/subgid").read_text() == "existing:200000:65536\n"
    assert "alice" not in host.accounts
    assert {str(path.relative_to(host.root)) for path in host.root.rglob("*") if path.is_file()} == {
        "etc/porelo-host/forge.conf",
        "etc/porelo-host/vpn.conf",
        "etc/subuid",
        "etc/subgid",
    }
    refused(host, capsys, 65, "purge", "alice", data=b"")


@pytest.mark.parametrize("verb", ["lock", "purge"])
def test_unknown_people_cannot_affect_unrelated_accounts(host, capsys, verb):
    """Prevent teardown verbs from disabling or deleting an account the helper does not manage."""
    host.accounts["alice"] = 1000
    refused(host, capsys, 65, verb, "alice", data=b"")


def test_missing_porelo_skips_only_its_optional_commands(host, capsys):
    """Prevent an absent Porelo binary from obstructing revocation or deleting a different program's data."""
    assert host.invoke("add", "alice", "--role", "project-admin") == 0
    host.commands.remove("porelo")
    host.calls.clear()
    assert host.invoke("purge", "alice", data=b"") == 0
    assert not any(args[0] == "runuser" for args in host.calls)
    assert not host.path("/etc/porelo-host/people/alice.conf").exists()


@pytest.mark.parametrize(
    "command",
    [["useradd"], ["wg", "set", "wg-porelo", "peer", wg_key(1), "allowed-ips"], ["loginctl", "enable-linger"]],
)
def test_failed_admission_never_publishes_a_record_or_command_output(host, capsys, command):
    """Prevent a failed privileged command from claiming admission or printing keys or service output."""
    host.fail = command
    host.failed_output = laptop() + "untrusted-token"
    assert host.invoke("add", "alice", "--role", "project-admin") == 69
    output = capsys.readouterr()
    assert not output.out
    assert "exit 1" in output.err
    record = host.path("/etc/porelo-host/people/alice.conf")
    assert not record.exists() or "locked=true" in record.read_text(), "a failed add never records an admission"
    assert ssh_key(1) not in output.err and wg_key(1) not in output.err and "untrusted-token" not in output.err


@pytest.mark.parametrize("hook", ["forge_admit", "matrix_issue"])
def test_a_failed_admission_after_the_account_is_locked_and_recorded_for_purge(host, capsys, hook):
    """Prevent a half-admitted account from keeping ssh and VPN access while every verb refuses it as unrecorded."""

    def unavailable(name, values):
        if name == hook:
            raise host.factory.__globals__["Refusal"]("service unavailable", 69)

    host.hook_inspect = unavailable
    assert host.invoke("add", "alice", "--role", "project-admin") == 69
    output = capsys.readouterr()
    assert not output.out and "service unavailable" in output.err and "purge" in output.err
    assert not host.path("/etc/ssh/authorized_keys/alice").exists()
    assert not host.path("/etc/wireguard/porelo-host-peers/alice.conf").exists()
    assert ["wg", "set", "wg-porelo", "peer", wg_key(1), "remove"] in host.calls
    assert ["usermod", "--lock", "--expiredate", "1", "alice"] in host.calls
    assert "locked=true" in host.path("/etc/porelo-host/people/alice.conf").read_text()
    host.hook_inspect = lambda name, values: None
    assert host.invoke("purge", "alice", data=b"") == 0
    assert "alice" not in host.accounts
    assert not host.path("/etc/porelo-host/people/alice.conf").exists()


def test_a_purge_failing_after_the_vault_expires_the_account_again(host, capsys):
    """Prevent a failed purge from leaving a locked person's account unexpired, which a later lock would not redo."""
    assert host.invoke("add", "alice", "--role", "project-admin") == 0
    assert host.invoke("lock", "alice", data=b"") == 0
    capsys.readouterr()
    host.calls.clear()
    host.fail = ["userdel"]
    assert host.invoke("purge", "alice", data=b"") == 69
    assert host.calls[-1] == ["usermod", "--expiredate", "1", "alice"], "the account left must be expired again"
    assert "locked=true" in host.path("/etc/porelo-host/people/alice.conf").read_text()


def test_purge_goes_on_when_logind_has_already_let_the_person_go(host, capsys):
    """Prevent a person without sessions or linger from making purge unfinishable."""
    assert host.invoke("add", "alice", "--role", "project-admin") == 0
    assert host.invoke("lock", "alice", data=b"") == 0
    capsys.readouterr()
    # Disabling linger lets logind drop a person without a session, and terminate-user then knows nobody.
    host.fail = ["loginctl", "terminate-user"]
    host.calls.clear()
    assert host.invoke("purge", "alice", data=b"") == 0
    assert host.calls[-2:] == [["systemctl", "stop", "user@1000.service"], ["userdel", "--remove", "alice"]]


def test_purge_without_porelo_still_stops_the_lingering_user_manager(host, capsys):
    """Prevent userdel from refusing an account whose manager linger started, when Porelo is not installed."""
    assert host.invoke("add", "alice", "--role", "project-admin") == 0
    host.commands.remove("porelo")
    host.calls.clear()
    assert host.invoke("purge", "alice", data=b"") == 0
    assert host.calls[-2:] == [["systemctl", "stop", "user@1000.service"], ["userdel", "--remove", "alice"]]


def test_people_are_told_from_system_accounts_by_the_hosts_own_uid_range(host, capsys):
    """Prevent a host with its own UID_MIN from having a service account treated as a person's."""
    host.write("/etc/login.defs", "# comment\nUID_MIN\t\t\t 2000\nUID_MAX 60000\n", 0o644)
    assert host.invoke("add", "alice", "--role", "project-admin") == 0
    capsys.readouterr()
    host.accounts["alice"] = 1500
    refused(host, capsys, 65, "purge", "alice", data=b"")


def test_keys_are_kept_only_in_the_access_files_and_record(host, capsys):
    """Prevent public key lines escaping into the interface's output or unrelated files."""
    assert host.invoke("add", "alice", "--role", "project-admin") == 0
    output = capsys.readouterr()
    assert ssh_key(1) not in output.out + output.err and wg_key(1) not in output.out + output.err
    allowed = {
        "etc/porelo-host/people/alice.conf",
        "etc/ssh/authorized_keys/alice",
        "etc/wireguard/porelo-host-peers/alice.conf",
    }
    found = {
        str(path.relative_to(host.root))
        for path in host.root.rglob("*")
        if path.is_file() and (ssh_key(1) in path.read_text() or wg_key(1) in path.read_text())
    }
    assert found == allowed


def test_useradd_cannot_allocate_unplanned_subordinate_ranges(host):
    """Prevent useradd's configured defaults from colliding with the ranges reserved before admission."""
    assert host.invoke("add", "alice", "--role", "project-admin") == 0
    assert "SUB_UID_COUNT=0" in host.calls[0] and "SUB_GID_COUNT=0" in host.calls[0]


@pytest.mark.parametrize(
    "text",
    [
        "role=project-admin\nprojects=\nlocked=false\n",
        "not-a-record\n",
        "role=project-admin\nprojects=unsafe\nlocked=false\nlaptop=" + laptop(address="10.73.7.3"),
        "role=project-admin\nprojects=\nlocked=maybe\nlaptop=" + laptop(address="10.73.7.3"),
        "role=project-admin\nprojects=\nlocked=false\nlaptop=" + laptop(address="10.73.8.3"),
    ],
    ids=["no-laptops", "bad-record", "unsupported-projects", "invalid-lock-state", "wrong-network"],
)
def test_malformed_records_cannot_be_ignored_during_allocation(host, capsys, text):
    """Prevent skipping an unreadable or inconsistent reservation and assigning another person its identity."""
    host.write("/etc/porelo-host/people/alice.conf", text)
    refused(host, capsys, 65, "add", "bob", "--role", "project-admin", data=laptop(number=2).encode())


def test_paths_owned_by_another_account_are_refused(host, capsys):
    """Prevent treating another account's directories or files as root's trusted configuration."""
    host.write("/etc/porelo-host/people/alice.conf", "bad-record\n")
    original = host.factory

    def wrong_owner(*args, **kwargs):
        kwargs["owner"] = os.getuid() + 1
        return original(*args, **kwargs)

    host.factory = wrong_owner
    refused(host, capsys, 69, "add", "bob", "--role", "project-admin")


def test_auto_allocation_skips_other_people_and_the_admin_and_exhaustion_refuses(host, capsys):
    """Prevent duplicate routes when addresses are occupied or the VPN subnet is full."""
    host.write("/etc/porelo-host/vpn.conf", "admin_address=10.73.7.4\n")
    data = "".join(laptop(f"device-{n}", n, f"10.73.7.{n + 4}") for n in range(1, 251))
    data += laptop("device-251", 251, "10.73.7.2")
    data += laptop("device-252", 252, "10.73.7.3")
    assert host.invoke("add", "alice", "--role", "project-admin", data=data.encode()) == 0
    capsys.readouterr()
    refused(host, capsys, 65, "add", "bob", "--role", "project-admin", data=laptop(number=253).encode())


def test_new_people_take_the_lowest_free_address_after_existing_reservations(host, capsys):
    """Prevent a later person's automatic allocation from displacing an existing laptop or the admin."""
    host.write("/etc/porelo-host/vpn.conf", "admin_address=10.73.7.4\n")
    assert host.invoke("add", "alice", "--role", "project-admin", data=laptop(address="10.73.7.2").encode()) == 0
    capsys.readouterr()
    data = (laptop(number=2) + laptop("second", 3)).encode()
    assert host.invoke("add", "bob", "--role", "project-admin", data=data) == 0
    addresses = [item["vpn_address"] for item in json.loads(capsys.readouterr().out)["laptops"]]
    assert addresses == ["10.73.7.3", "10.73.7.5"]


@pytest.mark.parametrize(
    "kind,text",
    [
        ("subuid", "bad\n"),
        ("subgid", "owner:1:0\n"),
        ("subuid", "owner:4294967290:3\n"),
        ("subgid", "owner:-1:65536\n"),
        ("subuid", "owner:" + "1" * 4400 + ":65536\n"),
    ],
    ids=["missing-fields", "zero-count", "exhaustion", "negative-id", "oversized-number"],
)
def test_invalid_or_exhausted_subordinate_ids_cannot_create_an_account(host, capsys, kind, text):
    """Prevent container ID overlap or overflow being discovered after a home and account exist."""
    host.write("/etc/" + kind, text, 0o644)
    refused(host, capsys, 69, "add", "alice", "--role", "project-admin")


def test_existing_people_group_and_missing_virtualization_groups_need_no_creation(host):
    """Prevent adding people to unavailable groups or recreating a group that already controls sudo access."""
    host.groups = {"porelo-people"}
    host.commands.remove("groupadd")
    assert host.invoke("add", "alice", "--role", "project-admin") == 0
    assert not any(args[0] == "groupadd" for args in host.calls)
    assert ["usermod", "--append", "--groups", "porelo-people", "alice"] in host.calls


def test_a_record_never_authorizes_root_or_a_system_uid(host, capsys):
    """Prevent a stale admission record from authorizing modifications to a reassigned system account."""
    assert host.invoke("add", "alice", "--role", "project-admin") == 0
    capsys.readouterr()
    host.accounts["alice"] = 999
    refused(host, capsys, 65, "purge", "alice", data=b"")


@pytest.mark.parametrize(
    "verb,missing",
    [("lock", "wg"), ("lock", "usermod"), ("lock", "runuser"), ("purge", "userdel"), ("purge", "runuser")],
)
def test_teardown_dependencies_are_checked_before_removing_access(host, capsys, verb, missing):
    """Prevent missing teardown programs from causing partial revocation or account loss."""
    assert host.invoke("add", "alice", "--role", "project-admin") == 0
    capsys.readouterr()
    host.commands.remove(missing)
    refused(host, capsys, 69, verb, "alice", data=b"")


def test_failed_peer_removal_still_disables_the_account_and_allows_retry(host, capsys):
    """Prevent a VPN failure from leaving SSH sessions enabled or being hidden by an idempotent lock."""
    assert host.invoke("add", "alice", "--role", "project-admin") == 0
    capsys.readouterr()
    host.calls.clear()
    host.fail = ["wg"]
    assert host.invoke("lock", "alice", data=b"") == 69
    assert ["usermod", "--lock", "--expiredate", "1", "alice"] in host.calls
    assert "locked=false" in host.path("/etc/porelo-host/people/alice.conf").read_text()
    assert not host.path("/etc/ssh/authorized_keys/alice").exists()
    assert not capsys.readouterr().out
    host.fail = None
    assert host.invoke("lock", "alice", data=b"") == 0
    assert "locked=true" in host.path("/etc/porelo-host/people/alice.conf").read_text()


def test_purge_clears_no_vault_while_a_task_of_the_person_still_runs(host, capsys):
    """Prevent clearing a vault whose token a surviving task still holds, as Porelo's lock-out order says."""
    assert host.invoke("add", "alice", "--role", "project-admin") == 0
    assert host.invoke("lock", "alice", data=b"") == 0
    capsys.readouterr()
    host.calls.clear()
    host.fail = ["runuser", "-u", "alice", "--", "env", "XDG_RUNTIME_DIR=/run/user/1000", "porelo", "task", "stop"]
    assert host.invoke("purge", "alice", data=b"") == 69
    assert not any("vault" in args for args in host.calls)
    assert not any(args[0] == "userdel" for args in host.calls)
    assert host.calls[-1] == ["usermod", "--expiredate", "1", "alice"], "the account left must be expired again"
    assert "alice" in host.accounts
    assert host.path("/etc/porelo-host/people/alice.conf").exists()


def test_failed_vault_clear_keeps_the_locked_account_and_record_for_retry(host, capsys):
    """Prevent account deletion before the person's vault has been cleared successfully."""
    assert host.invoke("add", "alice", "--role", "project-admin") == 0
    capsys.readouterr()
    host.calls.clear()
    host.fail = ["runuser", "-u", "alice", "--", "env", "XDG_RUNTIME_DIR=/run/user/1000", "porelo", "vault", "clear"]
    assert host.invoke("purge", "alice", data=b"") == 69
    assert not any(args[0] == "userdel" for args in host.calls)
    assert host.calls[-1] == ["usermod", "--expiredate", "1", "alice"], "the account left must be expired again"
    assert "locked=true" in host.path("/etc/porelo-host/people/alice.conf").read_text()
    assert "alice" in host.accounts
    host.fail = None
    host.calls.clear()
    assert host.invoke("purge", "alice", data=b"") == 0
    assert not any(args[0] == "wg" for args in host.calls)
    assert not host.path("/etc/porelo-host/people/alice.conf").exists()


def test_root_cli_has_no_test_switch_and_refuses_non_root_with_isolation():
    """Prevent a caller from using environment or CLI switches to bypass root and path checks."""
    if os.geteuid() == 0:
        pytest.skip("the unprivileged CLI check requires a non-root test process")
    result = subprocess.run(
        ["/usr/bin/python3", "-I", str(SCRIPT), "--test-root", "/tmp"],
        input=laptop(),
        text=True,
        capture_output=True,
        env={"PATH": "/untrusted", "PORELO_HOST_PERSON_TEST": "1"},
        check=False,
    )
    assert result.returncode == 69 and not result.stdout and "root" in result.stderr


def test_failed_write_does_not_leave_a_record_or_staged_key_file(host, capsys):
    """Prevent a failed publication from reporting admission or leaving another copy of the key block."""

    def obstruct_after_validation(args):
        if args[0] == "useradd":
            host.path("/etc/ssh/authorized_keys/alice").mkdir(parents=True)

    host.inspect = obstruct_after_validation
    assert host.invoke("add", "alice", "--role", "project-admin") == 73
    output = capsys.readouterr()
    assert not output.out and "cannot write" in output.err
    assert not list(host.root.rglob(".porelo-host-person.*"))
    assert "locked=true" in host.path("/etc/porelo-host/people/alice.conf").read_text()
    assert not any(args[0] == "wg" and "allowed-ips" in args for args in host.calls)


def test_recorded_person_without_an_account_cannot_be_readmitted(host, capsys):
    """Prevent restoring access against a missing or externally removed account while claiming idempotence."""
    assert host.invoke("add", "alice", "--role", "project-admin") == 0
    capsys.readouterr()
    del host.accounts["alice"]
    refused(host, capsys, 65, "add", "alice", "--role", "project-admin")


def test_purge_can_finish_after_userdel_succeeded_in_an_interrupted_run(host, capsys):
    """Prevent a completed account deletion from making the remaining record and subordinate IDs unremovable."""
    assert host.invoke("add", "alice", "--role", "project-admin") == 0
    assert host.invoke("lock", "alice", data=b"") == 0
    capsys.readouterr()
    del host.accounts["alice"]
    host.calls.clear()
    assert host.invoke("purge", "alice", data=b"") == 0
    assert host.calls == []
    assert not host.path("/etc/porelo-host/people/alice.conf").exists()


@pytest.mark.parametrize(
    "failure",
    [
        FileNotFoundError(),
        subprocess.TimeoutExpired("useradd", 60),
        UnicodeDecodeError("utf-8", b"\xffuntrusted-token", 0, 1, "invalid"),
    ],
    ids=["disappeared-command", "timeout", "unreadable-output"],
)
def test_command_runner_failures_do_not_escape_as_tracebacks_or_disclose_output(host, capsys, failure):
    """Prevent failed command startup, a hang or unreadable output from bypassing safe diagnostics."""

    def fail(args):
        raise failure

    host.inspect = fail
    assert host.invoke("add", "alice", "--role", "project-admin") == 69
    output = capsys.readouterr()
    assert not output.out and "useradd" in output.err
    assert "untrusted-token" not in output.err
    assert not host.path("/etc/porelo-host/people/alice.conf").exists()


@pytest.mark.parametrize("service", ["forge_lock", "matrix_expel_revoke"])
def test_failed_service_revocation_still_locks_the_host_account_for_retry(host, capsys, service):
    """Prevent a forge or homeserver failure from leaving SSH sessions and the Linux login enabled."""
    assert host.invoke("add", "alice", "--role", "project-admin") == 0
    capsys.readouterr()
    host.calls.clear()

    def unavailable(name, values):
        if name == service:
            raise host.factory.__globals__["Refusal"]("service unavailable", 69)

    host.hook_inspect = unavailable
    assert host.invoke("lock", "alice", data=b"") == 69
    assert ["usermod", "--lock", "--expiredate", "1", "alice"] in host.calls
    assert ["loginctl", "terminate-user", "alice"] in host.calls
    assert [
        "runuser",
        "-u",
        "alice",
        "--",
        "env",
        "XDG_RUNTIME_DIR=/run/user/1000",
        "porelo",
        "task",
        "stop",
        "--all",
    ] in host.calls
    assert "locked=false" in host.path("/etc/porelo-host/people/alice.conf").read_text()
    assert not capsys.readouterr().out


def test_service_configuration_is_validated_before_creating_an_account(host, capsys):
    """Prevent a missing Matrix machine name from leaving a newly admitted but unrecorded account."""
    host.write("/etc/porelo-host/forge.conf", "address=10.73.7.1\nhost=invalid/host\n")
    call = host.factory(
        host.root,
        host.run,
        euid=0,
        owner=os.getuid(),
        accounts=host.accounts,
        groups=host.groups,
        commands=host.commands,
        hooks=None,
    )
    assert call(["add", "alice", "--role", "project-admin"], laptop().encode()) == 69
    assert host.calls == []
    assert not host.path("/etc/ssh/authorized_keys/alice").exists()
    assert not capsys.readouterr().out


@pytest.mark.parametrize("verb", ["lock", "purge"])
def test_teardown_removes_a_locked_persons_runtime_delivery_directory(host, capsys, monkeypatch, verb):
    """Prevent a completed or retried teardown from leaving the person's delivered credentials behind."""
    assert host.invoke("add", "alice", "--role", "project-admin") == 0
    assert host.invoke("lock", "alice", data=b"") == 0
    capsys.readouterr()
    directory = host.path("/run/porelo-host/people/alice")
    directory.mkdir(parents=True, mode=0o700)
    for parent in (directory.parent, directory.parent.parent, host.path("/run")):
        parent.chmod(0o755)
    (directory / "identities.tokens").write_text("fixture credential")
    monkeypatch.setattr(
        host.factory.__globals__["pwd"],
        "getpwnam",
        lambda user: SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid(), pw_dir=str(host.root / "home/alice")),
    )
    assert host.invoke(verb, "alice", data=b"") == 0
    assert not directory.exists()
    assert ("alice" not in host.accounts) == (verb == "purge")


def test_legacy_record_is_read_as_hand_and_rewritten_on_its_next_write(host, capsys):
    """Prevent an existing record without member lines from losing admission or keeping the old shape on write."""
    host.accounts["alice"] = 1000
    host.write(
        "/etc/porelo-host/people/alice.conf",
        f"role=project-admin\nprojects=\nlocked=false\nlaptop=laptop {ssh_key(1)} {wg_key(1)} 10.73.7.3\n",
    )
    assert host.invoke("add", "alice", "--role", "project-admin") == 0
    assert json.loads(capsys.readouterr().out) == {
        "person": "alice",
        "role": "project-admin",
        "laptops": [{"laptop": "laptop", "vpn_address": "10.73.7.3"}],
    }
    assert host.calls == []
    assert host.invoke("lock", "alice", data=b"") == 0
    assert json.loads(capsys.readouterr().out) == {"person": "alice", "locked": True}
    assert host.path("/etc/porelo-host/people/alice.conf").read_text() == (
        f"member=hand\nlocked=true\nlaptop=laptop {ssh_key(1)} {wg_key(1)} 10.73.7.3\n"
    )


def test_add_adds_hand_in_fixed_order_to_a_person_who_holds_only_project_memberships(host, capsys):
    """Prevent admitting an existing project member by hand from dropping their projects or recreating the account."""
    host.accounts["alice"] = 1000
    record = host.path("/etc/porelo-host/people/alice.conf")
    host.write(
        "/etc/porelo-host/people/alice.conf",
        "member=alpha developer\n"
        "member=beta project-admin\n"
        "locked=false\n"
        f"laptop=laptop {ssh_key(1)} {wg_key(1)} 10.73.7.3\n",
    )
    refused(host, capsys, 65, "add", "alice", "--role", "project-admin", data=laptop(number=2).encode())
    assert "member=hand\n" not in record.read_text()
    assert host.invoke("add", "alice", "--role", "project-admin") == 0
    assert json.loads(capsys.readouterr().out) == {
        "person": "alice",
        "role": "project-admin",
        "laptops": [{"laptop": "laptop", "vpn_address": "10.73.7.3"}],
    }
    assert host.calls == [] and host.events == []
    assert record.read_text() == (
        "member=hand\n"
        "member=alpha developer\n"
        "member=beta project-admin\n"
        "locked=false\n"
        f"laptop=laptop {ssh_key(1)} {wg_key(1)} 10.73.7.3\n"
    )


def test_lock_keeps_every_membership_and_accepts_a_record_left_with_none(host, capsys):
    """Prevent lock from erasing memberships that block teardown, or rejecting a person left with no project."""
    host.accounts["alice"] = 1000
    host.accounts["bob"] = 1001
    host.write(
        "/etc/porelo-host/people/alice.conf",
        "member=hand\n"
        "member=alpha project-admin\n"
        "member=alpha developer\n"
        "locked=false\n"
        f"laptop=laptop {ssh_key(1)} {wg_key(1)} 10.73.7.3\n",
    )
    host.write(
        "/etc/porelo-host/people/bob.conf",
        f"locked=false\nlaptop=other {ssh_key(2)} {wg_key(2)} 10.73.7.4\n",
    )
    assert host.invoke("lock", "alice", data=b"") == 0
    assert json.loads(capsys.readouterr().out) == {"person": "alice", "locked": True}
    assert host.path("/etc/porelo-host/people/alice.conf").read_text() == (
        "member=hand\n"
        "member=alpha project-admin\n"
        "member=alpha developer\n"
        "locked=true\n"
        f"laptop=laptop {ssh_key(1)} {wg_key(1)} 10.73.7.3\n"
    )
    assert host.invoke("lock", "bob", data=b"") == 0
    assert json.loads(capsys.readouterr().out) == {"person": "bob", "locked": True}
    assert host.path("/etc/porelo-host/people/bob.conf").read_text() == (
        f"locked=true\nlaptop=other {ssh_key(2)} {wg_key(2)} 10.73.7.4\n"
    )


def test_failed_add_rollback_records_no_membership_on_the_locked_account(host, capsys):
    """Prevent a rolled-back failed admission from recording a membership for an account that was never admitted."""

    def obstruct_after_validation(args):
        if args[0] == "useradd":
            host.path("/etc/ssh/authorized_keys/alice").mkdir(parents=True)

    host.inspect = obstruct_after_validation
    assert host.invoke("add", "alice", "--role", "project-admin") == 73
    capsys.readouterr()
    text = host.path("/etc/porelo-host/people/alice.conf").read_text()
    assert text.startswith("locked=true\nlaptop=") and "member=" not in text and "role=" not in text
    host.inspect = lambda _args: None
    host.path("/etc/ssh/authorized_keys/alice").rmdir()
    assert host.invoke("purge", "alice", data=b"") == 0
    assert not host.path("/etc/porelo-host/people/alice.conf").exists()


@pytest.mark.parametrize(
    "members",
    [
        "role=project-admin\nprojects=\nmember=hand\n",
        "member=hand\nmember=hand\n",
        "member=alpha developer\nmember=hand\n",
        "member=beta project-admin\nmember=alpha project-admin\n",
        "member=alpha developer\nmember=alpha project-admin\n",
        "member=alpha owner\n",
        "member=Alpha developer\n",
        "member=\n",
    ],
    ids=[
        "mixed-legacy",
        "duplicate-hand",
        "hand-after-project",
        "unordered-projects",
        "developer-before-admin",
        "unknown-role",
        "uppercase-project",
        "empty-member",
    ],
)
def test_unordered_duplicate_or_unknown_memberships_are_refused(host, capsys, members):
    """Prevent malformed membership lines from being ignored during allocation or lock."""
    host.write(
        "/etc/porelo-host/people/alice.conf",
        members + f"locked=false\nlaptop=laptop {ssh_key(1)} {wg_key(1)} 10.73.7.3\n",
    )
    refused(host, capsys, 65, "add", "bob", "--role", "project-admin", data=laptop(number=2).encode())


CA_DER = b"fixture-host-ca-certificate-der-bytes"
CA_PEM = ssl.DER_cert_to_PEM_cert(CA_DER)
CA_SHA256 = hashlib.sha256(CA_DER).hexdigest()
HOST_WG_KEY = wg_key(200)
SIGNER_ONE = ssh_key(100)
SIGNER_TWO = ssh_key(101)
SIGNER_ROTATED = ssh_key(102)
FORGE_ADMIN_TOKEN = "f" * 40


def developer_laptop(number, address):
    return {
        "ssh_public_key": ssh_key(number),
        "wireguard_public_key": wg_key(number),
        "vpn_address": address,
    }


def host_block(network="10.73.7.0/24", wireguard_public_key=HOST_WG_KEY, ca_sha256=CA_SHA256):
    return {
        "address": "192.0.2.10",
        "endpoint": "192.0.2.10:51820",
        "wireguard_public_key": wireguard_public_key,
        "network": network,
        "ssh_host_key": ssh_key(201),
        "ca_sha256": ca_sha256,
    }


@pytest.fixture
def sync_host(host, monkeypatch):
    scope = host.factory.__globals__
    host.commands.update({"systemd-run", "podman"})
    host.write(
        "/etc/porelo-host/forge.conf",
        "address=10.73.7.1\nport=3000\naccount=porelo-forge\nagents=codex\nname=forge.example.org\nhost=host\n",
    )
    ca = host.write("/etc/porelo-host/forge/ca.pem", CA_PEM, 0o644)
    uid = os.getuid() or 1000
    gid = os.getgid()
    uid_overrides = {}

    def getpwnam(user):
        if user == "porelo-forge":
            return SimpleNamespace(pw_uid=1200, pw_gid=1200, pw_dir=str(host.root / "home/porelo-forge"))
        if user == "porelo-matrix":
            return SimpleNamespace(pw_uid=1201, pw_gid=1201, pw_dir=str(host.root / "home/porelo-matrix"))
        if user not in host.accounts:
            raise KeyError(user)
        return SimpleNamespace(
            pw_uid=uid_overrides.get(user, uid),
            pw_gid=gid,
            pw_dir=str(host.root / "home" / user),
        )

    monkeypatch.setattr(scope["pwd"], "getpwnam", getpwnam)

    for admin, project, signer, number, address in (
        ("ada", "alpha", SIGNER_ONE, 90, "10.73.7.3"),
        ("bo", "beta", SIGNER_TWO, 91, "10.73.7.4"),
    ):
        assert (
            host.invoke("add", admin, "--role", "project-admin", data=laptop(f"{admin}-laptop", number).encode()) == 0
        )
        record_path = host.path(f"/etc/porelo-host/people/{admin}.conf")
        record_path.write_text(
            f"member=hand\nmember={project} project-admin\nlocked=false\n"
            f"laptop={admin}-laptop {ssh_key(number)} {wg_key(number)} {address}\n"
        )
        host.write(
            f"/etc/porelo-host/projects/{project}.conf",
            f"admin={admin}\nsigned_by={signer}\npublisher=porelo-publisher-{project}\n",
        )
        setup_dir = host.root / "home" / admin / ".local/share/porelo-host/setup" / project
        for parent in reversed([setup_dir, *setup_dir.parents]):
            if host.root in parent.parents:
                parent.mkdir(exist_ok=True, mode=0o700)
                parent.chmod(0o700)
        for bundle in ("project.bundle", "access.bundle"):
            bundle_path = setup_dir / bundle
            bundle_path.write_bytes(f"{project}:{bundle}".encode())
            bundle_path.chmod(0o600)

    state = SimpleNamespace(
        verify_reply={
            "alpha": {
                "project": "alpha",
                "commit": "1" * 40,
                "access_commit": "2" * 40,
                "signer": SIGNER_ONE,
                "signers": [SIGNER_ONE],
                "host": host_block(),
                "developers": {},
                "transports": {},
            },
            "beta": {
                "project": "beta",
                "commit": "3" * 40,
                "access_commit": "4" * 40,
                "signer": SIGNER_TWO,
                "signers": [SIGNER_TWO],
                "host": host_block(),
                "developers": {},
                "transports": {},
            },
        },
        verify_exit=0,
        verify_stderr="",
        verify_calls=[],
        forge_requests=[],
        teams={
            "alpha": [
                {"id": 11, "name": "Owners", "members": ["ada"]},
                {"id": 12, "name": "developers", "members": []},
            ],
            "beta": [{"id": 21, "name": "Owners", "members": ["bo"]}, {"id": 22, "name": "developers", "members": []}],
        },
        uid_overrides=uid_overrides,
    )

    base_run = host.run

    def run(args, input=None):
        if args[:4] == ["wg", "show", "wg-porelo", "public-key"]:
            host.calls.append(args)
            host.events.append(args)
            return subprocess.CompletedProcess(args, 0, HOST_WG_KEY + "\n", "")
        if args[0] == "systemd-run":
            host.calls.append(args)
            host.events.append(args)
            state.verify_calls.append(args)
            assert "--pipe" in args and "--wait" in args and "--quiet" in args and "--collect" in args
            assert "DynamicUser=yes" in args
            assert "PrivateNetwork=yes" in args
            assert "ProtectHome=yes" in args
            project = args[args.index("--project") + 1]
            unit = f"porelo-host-sync-{project}"
            assert f"--unit={unit}" in args
            assert args[args.index("--repository") + 1] == f"/run/credentials/{unit}.service/project.bundle"
            assert args[args.index("--access-repository") + 1] == f"/run/credentials/{unit}.service/access.bundle"
            loaded = [arg.split(":", 1) for arg in args if arg.startswith("LoadCredential=")]
            assert len(loaded) == 2
            for name, copied in loaded:
                copied_path = Path(copied)
                assert copied_path.is_file() and not copied_path.is_symlink()
                assert host.path("/run/porelo-host/sync") in copied_path.parents
                assert stat.S_IMODE(copied_path.parent.stat().st_mode) == 0o700
                bundle = name.split("=", 1)[1]
                assert copied_path.read_bytes() == f"{project}:{bundle}".encode()
            if state.verify_exit:
                return subprocess.CompletedProcess(args, state.verify_exit, "", state.verify_stderr)
            return subprocess.CompletedProcess(args, 0, json.dumps(state.verify_reply[project]), "")
        if "podman" in args and "generate-access-token" in args:
            host.calls.append(args)
            host.events.append(args)
            return subprocess.CompletedProcess(args, 0, FORGE_ADMIN_TOKEN + "\n", "")
        return base_run(args)

    host.run = run

    class ForgeOpener:
        def open(self, request, timeout):
            assert timeout == 30
            assert request.get_header("Authorization") == "token " + FORGE_ADMIN_TOKEN
            url = urlsplit(request.full_url)
            assert (url.scheme, url.hostname, url.port) == ("https", "10.73.7.1", 3000)
            method, path = request.get_method(), url.path
            state.forge_requests.append((method, path))
            page = int(parse_qs(url.query).get("page", ["1"])[0])
            parts = path.removeprefix("/api/v1/").split("/")
            if method == "GET" and len(parts) == 3 and parts[0] == "orgs" and parts[2] == "teams":
                org = parts[1]
                if org not in state.teams:
                    raise urllib.error.HTTPError(request.full_url, 404, "not found", {}, io.BytesIO(b""))
                rows = [{"id": t["id"], "name": t["name"]} for t in state.teams[org]] if page == 1 else []
                reply = io.BytesIO(json.dumps(rows).encode())
                reply.status = 200
                return reply
            if len(parts) >= 3 and parts[0] == "teams" and parts[2] == "members":
                team_id = int(parts[1])
                team = next(t for org_teams in state.teams.values() for t in org_teams if t["id"] == team_id)
                if method == "GET" and len(parts) == 3:
                    rows = [{"login": login} for login in team["members"]] if page == 1 else []
                    reply = io.BytesIO(json.dumps(rows).encode())
                    reply.status = 200
                    return reply
                if method == "PUT" and len(parts) == 4:
                    if parts[3] not in team["members"]:
                        team["members"].append(parts[3])
                    reply = io.BytesIO(b"")
                    reply.status = 204
                    return reply
                if method == "DELETE" and len(parts) == 4:
                    if parts[3] in team["members"]:
                        team["members"].remove(parts[3])
                    reply = io.BytesIO(b"")
                    reply.status = 204
                    return reply
            raise AssertionError((method, path))

    def check_ca(*, cafile):
        assert cafile == str(ca)
        return ("CA", cafile)

    monkeypatch.setattr(scope["ssl"], "create_default_context", check_ca)
    monkeypatch.setattr(scope["urllib"].request, "HTTPSHandler", lambda *, context: context)
    monkeypatch.setattr(scope["urllib"].request, "build_opener", lambda *handlers: ForgeOpener())
    host.calls.clear()
    host.events.clear()
    return host, state


def forge_developers(state, project="alpha"):
    return next(team["members"] for team in state.teams[project] if team["name"] == "developers")


def test_sync_admits_a_developer_with_two_laptops_records_commits_and_updates_forge_team(sync_host, capsys):
    """Prevent sync from granting hand membership, ignoring a second laptop, using forge_login or leaving bundle copies."""
    host, state = sync_host
    capsys.readouterr()
    state.verify_reply["alpha"]["developers"] = {
        "dan": {
            "laptops": [developer_laptop(1, "10.73.7.10"), developer_laptop(2, "10.73.7.11")],
            "forge_login": "central-dan-ignored",
        }
    }
    assert host.invoke("sync", "alpha", data=b"") == 0
    out = capsys.readouterr()
    assert json.loads(out.out) == {
        "project": "alpha",
        "commit": "1" * 40,
        "access_commit": "2" * 40,
        "added": ["dan"],
        "dropped": [],
        "laptops_added": ["dan/l1", "dan/l2"],
        "laptops_dropped": [],
        "unchanged": False,
    }
    assert FORGE_ADMIN_TOKEN not in out.out + out.err
    assert "dan" in host.accounts
    assert host.path("/etc/porelo-host/people/dan.conf").read_text() == (
        "member=alpha developer\nlocked=false\n"
        f"laptop=l1 {ssh_key(1)} {wg_key(1)} 10.73.7.10\n"
        f"laptop=l2 {ssh_key(2)} {wg_key(2)} 10.73.7.11\n"
    )
    assert host.path("/etc/ssh/authorized_keys/dan").read_text() == (
        f'from="10.73.7.10" {ssh_key(1)}\nfrom="10.73.7.11" {ssh_key(2)}\n'
    )
    assert host.path("/etc/wireguard/porelo-host-peers/dan.conf").read_text() == (
        f"[Peer]\nPublicKey = {wg_key(1)}\nAllowedIPs = 10.73.7.10/32\n\n"
        f"[Peer]\nPublicKey = {wg_key(2)}\nAllowedIPs = 10.73.7.11/32\n\n"
    )
    assert ["wg", "set", "wg-porelo", "peer", wg_key(1), "allowed-ips", "10.73.7.10/32"] in host.calls
    assert ["wg", "set", "wg-porelo", "peer", wg_key(2), "allowed-ips", "10.73.7.11/32"] in host.calls
    assert any(event[:2] == ["forge_admit", "dan"] for event in host.events)
    assert ["matrix_issue", "dan"] in host.events
    assert forge_developers(state, "alpha") == ["dan"]
    assert host.path("/etc/porelo-host/projects/alpha.conf").read_text() == (
        f"admin=ada\nsigned_by={SIGNER_ONE}\npublisher=porelo-publisher-alpha\n"
        f"commit={'1' * 40}\naccess_commit={'2' * 40}\nsigner={SIGNER_ONE}\n"
    )
    assert list(host.path("/run/porelo-host/sync").iterdir()) == []


def test_sync_dropping_one_laptop_removes_only_that_laptops_access(sync_host, capsys):
    """Prevent dropping one laptop from locking the person or resetting their remaining laptop's SSH or VPN peer."""
    host, state = sync_host
    capsys.readouterr()
    state.verify_reply["alpha"]["developers"] = {
        "dan": {"laptops": [developer_laptop(1, "10.73.7.10"), developer_laptop(2, "10.73.7.11")], "forge_login": None}
    }
    assert host.invoke("sync", "alpha", data=b"") == 0
    capsys.readouterr()
    host.calls.clear()
    host.events.clear()

    state.verify_reply["alpha"]["access_commit"] = "5" * 40
    state.verify_reply["alpha"]["developers"] = {
        "dan": {"laptops": [developer_laptop(2, "10.73.7.11")], "forge_login": None}
    }
    assert host.invoke("sync", "alpha", data=b"") == 0
    assert json.loads(capsys.readouterr().out) == {
        "project": "alpha",
        "commit": "1" * 40,
        "access_commit": "5" * 40,
        "added": [],
        "dropped": [],
        "laptops_added": [],
        "laptops_dropped": ["dan/l1"],
        "unchanged": False,
    }
    verify_args = state.verify_calls[-1]
    assert verify_args[verify_args.index("--since") + 1] == "1" * 40
    assert verify_args[verify_args.index("--access-since") + 1] == "2" * 40
    wg_mutations = [args for args in host.calls if args[:3] == ["wg", "set", "wg-porelo"]]
    assert wg_mutations == [["wg", "set", "wg-porelo", "peer", wg_key(1), "remove"]]
    assert not any(event[0] in ("forge_lock", "matrix_expel_revoke", "useradd", "usermod") for event in host.events)
    assert host.path("/etc/ssh/authorized_keys/dan").read_text() == f'from="10.73.7.11" {ssh_key(2)}\n'
    assert host.path("/etc/wireguard/porelo-host-peers/dan.conf").read_text() == (
        f"[Peer]\nPublicKey = {wg_key(2)}\nAllowedIPs = 10.73.7.11/32\n\n"
    )
    assert host.path("/etc/porelo-host/people/dan.conf").read_text() == (
        f"member=alpha developer\nlocked=false\nlaptop=l2 {ssh_key(2)} {wg_key(2)} 10.73.7.11\n"
    )
    assert forge_developers(state, "alpha") == ["dan"]


def test_sync_dropping_a_developer_with_no_other_membership_locks_them(sync_host, capsys):
    """Prevent a dropped developer with no remaining membership from keeping SSH, VPN, forge or Matrix access."""
    host, state = sync_host
    capsys.readouterr()
    state.verify_reply["alpha"]["developers"] = {
        "dan": {"laptops": [developer_laptop(1, "10.73.7.10")], "forge_login": None}
    }
    assert host.invoke("sync", "alpha", data=b"") == 0
    capsys.readouterr()
    host.calls.clear()
    host.events.clear()

    state.verify_reply["alpha"]["access_commit"] = "6" * 40
    state.verify_reply["alpha"]["developers"] = {}
    assert host.invoke("sync", "alpha", data=b"") == 0
    assert json.loads(capsys.readouterr().out) == {
        "project": "alpha",
        "commit": "1" * 40,
        "access_commit": "6" * 40,
        "added": [],
        "dropped": ["dan"],
        "laptops_added": [],
        "laptops_dropped": [],
        "unchanged": False,
    }
    assert forge_developers(state, "alpha") == []
    assert not host.path("/etc/ssh/authorized_keys/dan").exists()
    assert not host.path("/etc/wireguard/porelo-host-peers/dan.conf").exists()
    assert ["wg", "set", "wg-porelo", "peer", wg_key(1), "remove"] in host.calls
    assert ["forge_lock", "dan"] in host.events
    assert ["matrix_expel_revoke", "dan"] in host.events
    assert ["usermod", "--lock", "--expiredate", "1", "dan"] in host.calls
    assert host.path("/etc/porelo-host/people/dan.conf").read_text() == (
        f"locked=true\nlaptop=l1 {ssh_key(1)} {wg_key(1)} 10.73.7.10\n"
    )
    assert "member=hand\nmember=alpha project-admin\nlocked=false\n" in (
        host.path("/etc/porelo-host/people/ada.conf").read_text()
    )


def test_sync_dropping_a_developer_still_in_another_project_keeps_their_host_access(sync_host, capsys):
    """Prevent dropping a developer from one project from revoking access they still hold through a second project."""
    host, state = sync_host
    capsys.readouterr()
    dan_spec = {"dan": {"laptops": [developer_laptop(1, "10.73.7.10")], "forge_login": None}}
    state.verify_reply["alpha"]["developers"] = dan_spec
    state.verify_reply["beta"]["developers"] = dan_spec
    assert host.invoke("sync", "alpha", data=b"") == 0
    assert host.invoke("sync", "beta", data=b"") == 0
    capsys.readouterr()
    assert host.path("/etc/porelo-host/people/dan.conf").read_text() == (
        "member=alpha developer\nmember=beta developer\nlocked=false\n"
        f"laptop=l1 {ssh_key(1)} {wg_key(1)} 10.73.7.10\n"
    )
    assert forge_developers(state, "alpha") == ["dan"]
    assert forge_developers(state, "beta") == ["dan"]

    host.calls.clear()
    host.events.clear()
    state.verify_reply["alpha"]["access_commit"] = "7" * 40
    state.verify_reply["alpha"]["developers"] = {}
    assert host.invoke("sync", "alpha", data=b"") == 0
    assert json.loads(capsys.readouterr().out) == {
        "project": "alpha",
        "commit": "1" * 40,
        "access_commit": "7" * 40,
        "added": [],
        "dropped": ["dan"],
        "laptops_added": [],
        "laptops_dropped": [],
        "unchanged": False,
    }
    assert forge_developers(state, "alpha") == []
    assert forge_developers(state, "beta") == ["dan"]
    assert not any(event[0] in ("forge_lock", "matrix_expel_revoke") for event in host.events)
    assert not any(args[:3] == ["wg", "set", "wg-porelo"] for args in host.calls)
    assert host.path("/etc/ssh/authorized_keys/dan").is_file()
    assert host.path("/etc/wireguard/porelo-host-peers/dan.conf").is_file()
    assert host.path("/etc/porelo-host/people/dan.conf").read_text() == (
        f"member=beta developer\nlocked=false\nlaptop=l1 {ssh_key(1)} {wg_key(1)} 10.73.7.10\n"
    )


def test_sync_adds_project_membership_to_a_hand_admitted_person_without_a_second_account_and_keeps_access_when_dropped(
    sync_host, capsys
):
    """Prevent sync from creating a duplicate account for a hand-admitted person or revoking their hand admission."""
    host, state = sync_host
    assert host.invoke("add", "cy", "--role", "project-admin", data=laptop("cy-laptop", 12, "10.73.7.12").encode()) == 0
    capsys.readouterr()
    host.calls.clear()
    host.events.clear()

    state.verify_reply["alpha"]["developers"] = {
        "cy": {"laptops": [developer_laptop(12, "10.73.7.12")], "forge_login": None}
    }
    assert host.invoke("sync", "alpha", data=b"") == 0
    assert json.loads(capsys.readouterr().out) == {
        "project": "alpha",
        "commit": "1" * 40,
        "access_commit": "2" * 40,
        "added": ["cy"],
        "dropped": [],
        "laptops_added": [],
        "laptops_dropped": [],
        "unchanged": False,
    }
    assert not any(args[0] == "useradd" for args in host.calls)
    assert forge_developers(state, "alpha") == ["cy"]
    assert host.path("/etc/porelo-host/people/cy.conf").read_text() == (
        "member=hand\nmember=alpha developer\nlocked=false\n"
        f"laptop=cy-laptop {ssh_key(12)} {wg_key(12)} 10.73.7.12\n"
    )

    host.calls.clear()
    host.events.clear()
    state.verify_reply["alpha"]["access_commit"] = "8" * 40
    state.verify_reply["alpha"]["developers"] = {}
    assert host.invoke("sync", "alpha", data=b"") == 0
    assert json.loads(capsys.readouterr().out) == {
        "project": "alpha",
        "commit": "1" * 40,
        "access_commit": "8" * 40,
        "added": [],
        "dropped": ["cy"],
        "laptops_added": [],
        "laptops_dropped": [],
        "unchanged": False,
    }
    assert forge_developers(state, "alpha") == []
    assert not any(event[0] in ("forge_lock", "matrix_expel_revoke") for event in host.events)
    assert host.path("/etc/ssh/authorized_keys/cy").is_file()
    assert host.path("/etc/wireguard/porelo-host-peers/cy.conf").is_file()
    assert host.path("/etc/porelo-host/people/cy.conf").read_text() == (
        f"member=hand\nlocked=false\nlaptop=cy-laptop {ssh_key(12)} {wg_key(12)} 10.73.7.12\n"
    )


def test_sync_refuses_when_porelo_verify_rejects_an_unknown_signer_and_cleans_temporary_bundles(sync_host, capsys):
    """Prevent bundles signed by an unpinned key from admitting anyone or leaving copied bundles in /run."""
    host, state = sync_host
    capsys.readouterr()
    before_etc = snapshot(host.path("/etc"))
    state.verify_exit = 65
    state.verify_stderr = "porelo: unknown_key: project commit signed by SHA256:other\n"
    assert host.invoke("sync", "alpha", data=b"") == 65
    output = capsys.readouterr()
    assert not output.out
    assert output.err.startswith("porelo-host-person: ") and "unknown_key" in output.err
    assert snapshot(host.path("/etc")) == before_etc
    assert state.forge_requests == []
    assert list(host.path("/run/porelo-host/sync").iterdir()) == []


@pytest.mark.parametrize(
    "override,expected_fields",
    [
        ({"network": "10.73.99.0/24"}, ["network"]),
        ({"wireguard_public_key": wg_key(250)}, ["wireguard_public_key"]),
        ({"ca_sha256": "0" * 64}, ["ca_sha256"]),
        (
            {"network": "10.73.99.0/24", "wireguard_public_key": wg_key(250), "ca_sha256": "0" * 64},
            ["network", "wireguard_public_key", "ca_sha256"],
        ),
        (None, ["host"]),
    ],
    ids=["wrong-network", "wrong-wg-key", "wrong-ca", "all-three-wrong", "missing-host"],
)
def test_sync_refuses_a_host_block_for_another_host_naming_every_differing_field(
    sync_host, capsys, override, expected_fields
):
    """Prevent replaying another host's signed access file on this host."""
    host, state = sync_host
    capsys.readouterr()
    state.verify_reply["alpha"]["host"] = None if override is None else host_block(**override)
    state.verify_reply["alpha"]["developers"] = {
        "dan": {"laptops": [developer_laptop(1, "10.73.7.10")], "forge_login": None}
    }
    before_etc = snapshot(host.path("/etc"))
    assert host.invoke("sync", "alpha", data=b"") == 65
    output = capsys.readouterr()
    assert not output.out
    assert output.err.startswith("porelo-host-person: ")
    for field in expected_fields:
        assert field in output.err
    assert "dan" not in host.accounts
    assert snapshot(host.path("/etc")) == before_etc
    assert state.forge_requests == []


def test_sync_checks_the_whole_diff_and_refuses_all_when_any_entry_conflicts(sync_host, capsys):
    """Prevent partial admission when any developer in the signed list collides with host records, accounts or network."""
    host, state = sync_host
    assert (
        host.invoke("add", "eve", "--role", "project-admin", data=laptop("eve-laptop", 30, "10.73.7.30").encode()) == 0
    )
    assert host.invoke("lock", "eve", data=b"") == 0
    capsys.readouterr()
    before_etc = snapshot(host.path("/etc"))
    before_accounts = dict(host.accounts)

    state.verify_reply["alpha"]["developers"] = {
        "eli": {"laptops": [developer_laptop(1, "10.73.7.10")], "forge_login": None},
        "taken": {"laptops": [developer_laptop(2, "10.73.7.3")], "forge_login": None},
    }
    assert host.invoke("sync", "alpha", data=b"") == 65
    output = capsys.readouterr()
    assert not output.out and "taken" in output.err and "10.73.7.3" in output.err
    assert "eli" not in host.accounts and host.accounts == before_accounts
    assert snapshot(host.path("/etc")) == before_etc
    assert forge_developers(state, "alpha") == []

    state.verify_reply["alpha"]["developers"] = {
        "eve": {"laptops": [developer_laptop(3, "10.73.7.11")], "forge_login": None},
        "daemon": {"laptops": [developer_laptop(4, "10.73.7.12")], "forge_login": None},
        "kvm": {"laptops": [developer_laptop(5, "10.73.7.13")], "forge_login": None},
        "outside": {"laptops": [developer_laptop(6, "10.73.8.14")], "forge_login": None},
        "reserved": {"laptops": [developer_laptop(7, "10.73.7.1")], "forge_login": None},
        "keysteal": {
            "laptops": [
                {"ssh_public_key": ssh_key(90), "wireguard_public_key": wg_key(8), "vpn_address": "10.73.7.15"}
            ],
            "forge_login": None,
        },
    }
    assert host.invoke("sync", "alpha", data=b"") == 65
    output = capsys.readouterr()
    assert not output.out
    for offending in ("eve", "purge", "daemon", "kvm", "outside", "reserved", "keysteal"):
        assert offending in output.err, (offending, output.err)
    assert host.accounts == before_accounts
    assert snapshot(host.path("/etc")) == before_etc


def test_sync_refuses_when_the_forges_developers_team_is_missing(sync_host, capsys):
    """Prevent admitting developers on the host before bring has created the project's developers team on the forge."""
    host, state = sync_host
    capsys.readouterr()
    state.teams["alpha"] = [{"id": 11, "name": "Owners", "members": ["ada"]}]
    state.verify_reply["alpha"]["developers"] = {
        "dan": {"laptops": [developer_laptop(1, "10.73.7.10")], "forge_login": None}
    }
    before_etc = snapshot(host.path("/etc"))
    assert host.invoke("sync", "alpha", data=b"") == 65
    output = capsys.readouterr()
    assert not output.out and "developers" in output.err and "run bring first" in output.err
    assert "dan" not in host.accounts
    assert snapshot(host.path("/etc")) == before_etc


def test_sync_with_unchanged_commits_changes_nothing_and_uses_rotated_signers(sync_host, capsys):
    """Prevent an unchanged timer run from rewriting records or minting forge tokens, and pass rotated signers next."""
    host, state = sync_host
    capsys.readouterr()
    state.verify_reply["alpha"]["signers"] = [SIGNER_ONE, SIGNER_ROTATED]
    state.verify_reply["alpha"]["developers"] = {
        "dan": {"laptops": [developer_laptop(1, "10.73.7.10")], "forge_login": None}
    }
    assert host.invoke("sync", "alpha", data=b"") == 0
    capsys.readouterr()

    before_etc = snapshot(host.path("/etc"))
    host.calls.clear()
    host.events.clear()
    state.forge_requests.clear()
    assert host.invoke("sync", "alpha", data=b"") == 0
    assert json.loads(capsys.readouterr().out) == {
        "project": "alpha",
        "commit": "1" * 40,
        "access_commit": "2" * 40,
        "added": [],
        "dropped": [],
        "laptops_added": [],
        "laptops_dropped": [],
        "unchanged": True,
    }
    verify_args = state.verify_calls[-1]
    signed_by = [verify_args[index + 1] for index, arg in enumerate(verify_args) if arg == "--signed-by"]
    assert signed_by == [SIGNER_ONE, SIGNER_ROTATED]
    assert verify_args[verify_args.index("--since") + 1] == "1" * 40
    assert verify_args[verify_args.index("--access-since") + 1] == "2" * 40
    assert snapshot(host.path("/etc")) == before_etc
    assert state.forge_requests == []
    assert not any("podman" in args or args[0] == "useradd" for args in host.calls)


def test_sync_via_sudo_allows_only_the_projects_unlocked_admin_and_checks_bundle_ownership(sync_host, capsys):
    """Prevent another person from syncing a project through sudo, or root from reading symlinked or writable bundles."""
    host, state = sync_host
    capsys.readouterr()
    state.verify_reply["alpha"]["developers"] = {
        "dan": {"laptops": [developer_laptop(1, "10.73.7.10")], "forge_login": None}
    }
    before_etc = snapshot(host.path("/etc"))

    assert host.invoke("sync", "unknown", data=b"") == 65
    assert "unknown" in capsys.readouterr().err
    assert snapshot(host.path("/etc")) == before_etc

    for caller in ("bo", "ghost", ""):
        assert host.invoke("sync", "alpha", data=b"", sudo_user=caller) == 65
        out = capsys.readouterr()
        assert not out.out and out.err.startswith("porelo-host-person: ")
        assert snapshot(host.path("/etc")) == before_etc

    setup_dir = host.root / "home/ada/.local/share/porelo-host/setup/alpha"
    bundle = setup_dir / "access.bundle"
    bundle.chmod(0o620)
    assert host.invoke("sync", "alpha", data=b"", sudo_user="ada") == 65
    assert not capsys.readouterr().out
    bundle.chmod(0o600)

    outside = host.root / "home/bo/.local/share/porelo-host/setup/beta/access.bundle"
    bundle.unlink()
    bundle.symlink_to(outside)
    assert host.invoke("sync", "alpha", data=b"", sudo_user="ada") == 65
    assert not capsys.readouterr().out
    bundle.unlink()
    bundle.write_bytes(b"alpha:access.bundle")
    bundle.chmod(0o600)

    moved_setup = host.root / "home/ada/.local/share/porelo-host/setup-real"
    setup_dir.parent.rename(moved_setup)
    (host.root / "home/ada/.local/share/porelo-host/setup").symlink_to(moved_setup)
    assert host.invoke("sync", "alpha", data=b"", sudo_user="ada") == 65
    assert not capsys.readouterr().out
    (host.root / "home/ada/.local/share/porelo-host/setup").unlink()
    moved_setup.rename(setup_dir.parent)

    state.uid_overrides["ada"] = (os.getuid() or 1000) + 1
    assert host.invoke("sync", "alpha", data=b"", sudo_user="ada") == 65
    assert not capsys.readouterr().out
    state.uid_overrides.pop("ada")
    assert snapshot(host.path("/etc")) == before_etc

    assert host.invoke("sync", "alpha", data=b"", sudo_user="ada") == 0
    assert json.loads(capsys.readouterr().out)["added"] == ["dan"]

    ada_record = host.path("/etc/porelo-host/people/ada.conf")
    ada_record.write_text(ada_record.read_text().replace("locked=false", "locked=true"))
    state.verify_reply["alpha"]["access_commit"] = "9" * 40
    assert host.invoke("sync", "alpha", data=b"", sudo_user="ada") == 65
    assert not capsys.readouterr().out
