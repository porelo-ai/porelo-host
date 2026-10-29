"""Exercise root admission and revocation against an isolated filesystem and command recorder."""

import base64
import json
import os
import runpy
import stat
import struct
import subprocess
from pathlib import Path
from types import SimpleNamespace

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
        self.commands = {"useradd", "usermod", "userdel", "loginctl", "groupadd", "wg", "runuser", "porelo"}
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

    def invoke(self, *args, data=None):
        def hook(name, values):
            self.hook_inspect(name, values)
            self.events.append([name, *values])

        hooks = {
            name: lambda *values, name=name: hook(name, values)
            for name in ("forge_admit", "matrix_issue", "forge_lock", "matrix_expel_revoke")
        }
        return self.factory(
            self.root,
            self.run,
            euid=self.euid,
            owner=os.getuid(),
            accounts=self.accounts,
            groups=self.groups,
            commands=self.commands,
            hooks=hooks,
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


def refused(host, capsys, code, *args, data=None, diagnostic=None):
    before = snapshot(host.root)
    host.calls.clear()
    host.events.clear()
    assert host.invoke(*args, data=data) == code
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
        ("sync", "alice"),
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
        "role=project-admin\nprojects=\nlocked=false\n"
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
        ["runuser", "-u", "alice", "--", "porelo", "task", "stop", "--all"],
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
    assert host.invoke("add", "alice", "--role", "project-admin") == 0
    assert snapshot(host.root) == before and host.events == []
    assert json.loads(capsys.readouterr().out) == {
        "person": "alice",
        "role": "project-admin",
        "laptops": [{"laptop": "laptop", "vpn_address": "10.73.7.3"}],
    }


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
    assert host.calls[-4:] == [
        ["usermod", "--lock", "--expiredate", "1", "alice"],
        ["runuser", "-u", "alice", "--", "porelo", "vault", "clear"],
        ["loginctl", "disable-linger", "alice"],
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


@pytest.mark.parametrize("command", [["useradd"], ["wg"], ["loginctl", "enable-linger"]])
def test_failed_admission_never_publishes_a_record_or_command_output(host, capsys, command):
    """Prevent a failed privileged command from claiming admission or printing keys or service output."""
    host.fail = command
    host.failed_output = laptop() + "untrusted-token"
    assert host.invoke("add", "alice", "--role", "project-admin") == 69
    output = capsys.readouterr()
    assert not output.out
    assert "exit 1" in output.err
    assert not host.path("/etc/porelo-host/people/alice.conf").exists()
    assert ssh_key(1) not in output.err and wg_key(1) not in output.err and "untrusted-token" not in output.err


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


def test_failed_vault_clear_keeps_the_locked_account_and_record_for_retry(host, capsys):
    """Prevent account deletion before the person's vault has been cleared successfully."""
    assert host.invoke("add", "alice", "--role", "project-admin") == 0
    capsys.readouterr()
    host.calls.clear()
    host.fail = ["runuser", "-u", "alice", "--", "porelo", "vault", "clear"]
    assert host.invoke("purge", "alice", data=b"") == 69
    assert not any(args[0] == "userdel" for args in host.calls)
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
    assert not host.path("/etc/porelo-host/people/alice.conf").exists()
    assert not any(args[0] == "wg" for args in host.calls)


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
    assert ["runuser", "-u", "alice", "--", "porelo", "task", "stop", "--all"] in host.calls
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
