"""Exercise root admission and revocation against an isolated filesystem and command recorder."""

import datetime
import base64
import hashlib
import io
import json
import os
import sys
import runpy
import stat
import struct
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
import pytest

from porelo_host_person_follow_support import prepare_follow

ROOT = Path(__file__).resolve().parents[3]


SCRIPT = ROOT / "roles/porelo/files/porelo-host-person"


def ssh_key(number):
    kind = b"ssh-ed25519"
    blob = struct.pack(">I", len(kind)) + kind + struct.pack(">I", 32) + bytes([number]) * 32
    return "ssh-ed25519 " + base64.b64encode(blob).decode()


def snapshot(root):
    return {
        str(path.relative_to(root)): (
            stat.S_IMODE(path.lstat().st_mode),
            path.lstat().st_mtime_ns,
            path.read_bytes() if path.is_file() and not path.is_symlink() else None,
        )
        for path in root.rglob("*")
    }


def as_alice(host, *words):
    """Porelo as alice the way root starts it: in `/`, with her own home and her user manager's runtime and bus."""
    return [
        "runuser",
        "-u",
        "alice",
        "--",
        "env",
        "-C",
        "/",
        f"HOME={host.root / 'home' / 'alice'}",
        "XDG_RUNTIME_DIR=/run/user/1000",
        "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus",
        "porelo",
        *words,
    ]


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
            "ssh-keygen",
            "gpasswd",
            "runuser",
            "env",
            "porelo",
            "systemctl",
            "/usr/libexec/porelo/transports/porelo-message-transport-matrix",
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

    def run(self, args, input=None):
        self.calls.append(args)
        self.events.append(args)
        self.inspect(args)
        if self.fail and args[: len(self.fail)] == self.fail:
            return subprocess.CompletedProcess(args, 1, self.failed_output, self.failed_output)
        if args[0] == "ssh-keygen":
            return subprocess.run(args, input=input, text=True, capture_output=True, check=False)
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
            for name in ("forge_admit", "forge_lock", "matrix_expel_revoke", "forge_drop_tokens")
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
        )(list(args), b"" if data is None else data)

    def apply(self, operation):
        """Call the integration methods used by follow with the isolated account and command recorder."""
        scope = self.factory.__globals__
        person = scope["Host"]()
        person.root, person.runner, person.euid = self.root, self.run, self.euid
        person.owner, person.group = os.getuid(), os.getgid()
        person.accounts, person.groups, person.commands = self.accounts, self.groups, self.commands

        def hook(name, values):
            self.hook_inspect(name, values)
            self.events.append([name, *values])

        person.hooks = {name: lambda *values, name=name: hook(name, values) for name in person.hooks}
        try:
            operation(person)
        except scope["Refusal"] as error:
            print(f"porelo-host-person: {error}", file=sys.stderr)
            return error.code
        except OSError:
            print("porelo-host-person: cannot read or change the host's files", file=sys.stderr)
            return 73
        return 0

    def admit(self, user="alice"):
        """Reach admission through follow's integration method with a verified fixture card."""

        def admission(person):
            person.check(person.path("/etc/porelo-host/forge.conf"), required=True)
            card = {"ssh": ssh_key(1), "expires": None}
            assert not person.key_revoked(card["ssh"])
            records = person.records()
            person.follow_admit(user, records.get(user), ["host-admin"], card, self.groups, records, self.accounts)

        return self.apply(admission)

    def revoke(self, user="alice", porelo=None):
        """Reach the lock method used by follow without a dispatcher verb."""

        def removal(person):
            record = person.records()[user]
            record["reason"] = "membership"
            person.lock(user, record, porelo)

        return self.apply(removal)


@pytest.fixture
def host(tmp_path, monkeypatch):
    namespace = runpy.run_path(str(SCRIPT), run_name="person_unit_tests")
    h = Host(tmp_path, namespace["_test_entry"])
    for uid in (1200, 1201):  # The service accounts' user managers, each with its session bus.
        (tmp_path / f"run/user/{uid}").mkdir(parents=True, exist_ok=True)
        os.mknod(tmp_path / f"run/user/{uid}/bus", stat.S_IFSOCK | 0o600)
    monkeypatch.setattr(
        namespace["pwd"],
        "getpwnam",
        lambda user: SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid(), pw_dir=str(tmp_path / "home" / user)),
    )
    for name in ("run", "run/user", "run/user/1200", "run/user/1201"):
        h.path("/" + name).chmod(0o755)
    h.write("/etc/porelo-host/forge.conf", "address=192.0.2.1\n")
    h.write("/etc/subuid", "existing:100000:65536\n", 0o644)
    h.write("/etc/subgid", "existing:200000:65536\n", 0o644)
    h.write(
        "/etc/porelo-host/organization/applied.json",
        json.dumps(
            {
                "commit": "a" * 40,
                "projects": [],
                "revoked": [],
                "persons": [
                    {"login": user, "ssh": ssh_key(number), "expires": None, "revoked": False}
                    for number, user in enumerate(("alice", "bob", "operator"), 1)
                ],
            }
        ),
    )
    krl = h.path("/etc/ssh/porelo-revoked.krl")
    h.write("/etc/ssh/empty", "")
    made = subprocess.run(
        ["ssh-keygen", "-q", "-k", "-f", str(krl), str(krl.parent / "empty")], capture_output=True, check=False
    )
    assert made.returncode == 0
    (krl.parent / "empty").unlink()
    return h


def refused(host, capsys, code, *args, data=None, diagnostic=None, sudo_user=None, operation=None):
    before = snapshot(host.root)
    host.calls.clear()
    host.events.clear()
    result = operation() if operation is not None else host.invoke(*args, data=data, sudo_user=sudo_user)
    assert result == code
    output = capsys.readouterr()
    assert not output.out, "a refusal must never answer success"
    assert output.err.startswith("porelo-host-person: ")
    if diagnostic:
        assert diagnostic in output.err
    assert snapshot(host.root) == before, "refusal must leave every file, directory, mode and mtime alone"
    assert all(call[:2] == ["ssh-keygen", "-Q"] for call in host.calls), "refusal must precede changes"
    assert all(event[:2] == ["ssh-keygen", "-Q"] for event in host.events), "refusal must precede hooks"
    return output


@pytest.mark.parametrize(
    "arguments",
    [
        ("registry", "status"),
        ("registry", "pin", "alice", ssh_key(1)),
        ("registry",),
        ("registry", "--stdin"),
        None,
    ],
    ids=["old-status", "old-pin", "old-bare", "old-stdin", "old-state"],
)
def test_obsolete_commands_and_state_cannot_supply_host_authority(host, capsys, arguments):
    """Prevent obsolete commands or stale pins and cards from granting host authority after the hard cut."""
    host.write("/etc/porelo-host/forge.conf", "address=192.0.2.1\nhost=host\n")
    host.path("/etc/porelo-host/organization/applied.json").unlink(missing_ok=True)
    host.write("/etc/porelo-host/registry/pin.conf", f"admin=alice\nkey={ssh_key(1)}\n")
    host.write(
        "/etc/porelo-host/registry/applied.json",
        json.dumps(
            {
                "commit": "a" * 40,
                "projects": [],
                "revoked": [],
                "persons": [{"login": "alice", "ssh": ssh_key(1), "expires": None, "revoked": False}],
            }
        ),
    )
    if arguments is not None:
        refused(host, capsys, 64, *arguments, data=b"bundle", diagnostic="use purge")
        return

    before = snapshot(host.root)
    assert host.invoke("org", "status", data=b"") == 0
    assert json.loads(capsys.readouterr().out) == {
        "host": "host",
        "organization": None,
        "refused": None,
        "commit": None,
        "pinned": None,
        "persons": [],
        "projects": [],
    }
    assert snapshot(host.root) == before, "status must leave stale state untouched"
    refused(host, capsys, 69, "org", "follow", data=b"", diagnostic="systemd-run")


def test_non_root_is_refused_before_reading_configuration_or_input(host, capsys):
    """Prevent an unprivileged invocation from reaching records or any account operation."""
    host.euid = 1000
    host.path("/etc/porelo-host/forge.conf").unlink()
    refused(host, capsys, 69, "purge", "alice", data=b"\xff", diagnostic="root")


def test_root_cli_has_no_test_switch_and_refuses_non_root_with_isolation():
    """Prevent a caller from using environment or CLI switches to bypass root and path checks."""
    if os.geteuid() == 0:
        pytest.skip("the unprivileged CLI check requires a non-root test process")
    result = subprocess.run(
        ["/usr/bin/python3", "-I", str(SCRIPT), "--test-root", "/tmp"],
        input="obsolete device input",
        text=True,
        capture_output=True,
        env={"PATH": "/untrusted", "PORELO_HOST_PERSON_TEST": "1"},
        check=False,
    )
    assert result.returncode == 69 and not result.stdout and "root" in result.stderr


SIGNER_ONE = ssh_key(100)


SIGNER_TWO = ssh_key(101)


SIGNER_ROTATED = ssh_key(102)


FORGE_ADMIN_TOKEN = "0" * 40


def fingerprint(key):
    blob = base64.b64decode(key.split(" ", 1)[1])
    return "SHA256:" + base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip("=")


@pytest.fixture
def follow_host(host, monkeypatch):
    scope = host.factory.__globals__
    initialize = scope["Host"].__init__

    def initialized(person):
        initialize(person)
        person.now = lambda: datetime.datetime(2026, 10, 30, tzinfo=datetime.timezone.utc)

    monkeypatch.setattr(scope["Host"], "__init__", initialized)
    for name in ("run", "run/user", "run/user/1200", "run/user/1201"):
        host.path("/" + name).chmod(0o755)
    host.commands.update({"systemd-run", "podman"})
    host.write(
        "/etc/porelo-host/forge.conf",
        "address=192.0.2.1\nport=3000\naccount=porelo-forge\nagents=codex\nname=forge.example.org\nhost=host\n",
    )
    uid = os.getuid() or 1000
    gid = os.getgid()
    uid_overrides = {}

    def getpwnam(user):
        if user == "porelo-forge":
            return SimpleNamespace(pw_uid=1200, pw_gid=1200, pw_dir=str(host.root / "home/porelo-forge"))
        if user == "porelo-matrix":
            return SimpleNamespace(pw_uid=1201, pw_gid=os.getgid(), pw_dir=str(host.root / "home/porelo-matrix"))
        if user not in host.accounts:
            raise KeyError(user)
        return SimpleNamespace(
            pw_uid=uid_overrides.get(user, uid),
            pw_gid=gid,
            pw_dir=str(host.root / "home" / user),
        )

    monkeypatch.setattr(scope["pwd"], "getpwnam", getpwnam)

    for admin, project, signer, number in (
        ("alice", "alpha", SIGNER_ONE, 90),
        ("bob", "beta", SIGNER_TWO, 91),
    ):
        host.accounts[admin] = 1000 + number
        host.write(
            f"/etc/porelo-host/people/{admin}.conf",
            f"member=host-admin\nmember={project} project-admin\nlocked=false\nssh={ssh_key(number)}\nexpires=\n",
        )
        host.write(
            f"/etc/porelo-host/projects/{project}.conf",
            f"admin={admin}\nsigned_by={signer}\npublisher=porelo-publisher-{project}\n",
        )
    state = SimpleNamespace(
        forge_requests=[],
        teams={
            "alpha": [
                {"id": 11, "name": "Owners", "members": ["alice"]},
                {"id": 12, "name": "developers", "members": []},
            ],
            "beta": [{"id": 21, "name": "Owners", "members": ["bob"]}, {"id": 22, "name": "developers", "members": []}],
        },
        uid_overrides=uid_overrides,
    )

    base_run = host.run

    def run(args, input=None):
        if "podman" in args and args[-1] == "list":
            names = set(host.accounts) | {"porelo-" + user for user in host.accounts} | {"codex-carol"}
            text = "ID Username Email\n" + "".join(
                f"{number} {user} {user}@forge.example.org\n" for number, user in enumerate(sorted(names), 1)
            )
            return subprocess.CompletedProcess(args, 0, text, "")
        if "podman" in args and "generate-access-token" in args:
            host.calls.append(args)
            host.events.append(args)
            return subprocess.CompletedProcess(args, 0, FORGE_ADMIN_TOKEN + "\n", "")
        return base_run(args, input=input)

    host.run = run

    class ForgeOpener:
        def open(self, request, timeout):
            assert timeout == 30
            assert request.get_header("Authorization") == "token " + FORGE_ADMIN_TOKEN
            url = urlsplit(request.full_url)
            assert (url.scheme, url.hostname, url.port) == ("http", "localhost", None)
            method, path = request.get_method(), url.path
            state.forge_requests.append((method, path))
            page = int(parse_qs(url.query).get("page", ["1"])[0])
            parts = path.removeprefix("/api/v1/").split("/")
            if method == "GET" and parts[0] == "orgs" and (len(parts) == 2 or parts[2] == "repos"):
                reply = io.BytesIO(b"{}" if len(parts) == 2 else b"[]")
                reply.status = 200
                return reply
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
                    names = set(host.accounts) | {"porelo-" + user for user in host.accounts} | {"codex-carol"}
                    if parts[3] not in names:
                        raise urllib.error.HTTPError(request.full_url, 404, "no user", {}, io.BytesIO(b""))
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
            if path.startswith("/api/v1/admin/users/porelo-admin/tokens"):
                reply = io.BytesIO(b"[]" if method == "GET" else b"")
                reply.status = 200 if method == "GET" else 204
                return reply
            raise AssertionError((method, path))

    monkeypatch.setattr(scope["urllib"].request, "build_opener", lambda *handlers: ForgeOpener())
    reply = {
        "revision": "a" * 40,
        "host_card": {"host": "host", "services": {"forge": {"web_port": 3000, "git_port": 2222}}},
        "admins": [{"login": "alice", "key": SIGNER_ONE, "fingerprint": fingerprint(SIGNER_ONE), "backup": False}],
        "persons": [org_person("alice", SIGNER_ONE), org_person("bob", SIGNER_TWO)],
        "projects": [
            {
                "project": project,
                "address": f"git@example.org:acme/{project}.git",
                "members": [{"login": admin, "role": "admin", "locked": False}],
                "signing_keys": [],
            }
            for project, admin in (("alpha", "alice"), ("beta", "bob"))
        ],
    }

    def record(args, input):
        host.calls.append(args)
        host.events.append(args)

    state.follow = prepare_follow(
        host, reply, record, host.run, {name: {"signers": "", "certifiers": ""} for name in ("alpha", "beta")}
    )
    host.run = state.follow
    host.write(
        "/etc/porelo-host/forge.conf",
        "address=192.0.2.1\nport=3000\ngit_port=2222\naccount=porelo-forge\n"
        "agents=codex\nname=forge.example.org\nhost=host\n",
    )
    host.write("/etc/porelo-host/forge/central-ca.conf", "/etc/porelo-host/forge/central-ca.pem\n")
    host.calls.clear()
    host.events.clear()
    return host, state


def org_person(login, key, revoked=False):
    return {"login": login, "key": key, "expires": "2027-10-30", "revoked": revoked}


@pytest.fixture
def org_host(follow_host):
    """A host with fictional accounts, a pinned admin and supplied organization command replies."""
    return follow_host


def applied(host):
    path = host.path("/etc/porelo-host/organization/applied.json")
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o711
    return json.loads(path.read_text())


def test_follow_fetches_against_the_pin_and_records_it_root_only(org_host, capsys):
    """Prevent the host from taking projects or persons without Porelo fetching against the pinned trust set."""
    host, state = org_host
    assert host.invoke("org", "follow", data=b"") == 0
    answer = json.loads(capsys.readouterr().out)
    assert answer["commit"] == "a" * 40 and answer["pinned"] == fingerprint(SIGNER_ONE)
    assert [p["project"] for p in answer["projects"]] == ["alpha", "beta"]
    assert [(p["login"], p["state"]) for p in answer["persons"]] == [("alice", "active"), ("bob", "active")]
    fetch = state.follow.fetches[0]
    assert state.follow.pins == [f"alice {SIGNER_ONE}\n"]
    assert "--since" not in fetch
    recorded = applied(host)
    assert recorded["commit"] == "a" * 40
    assert [project["project"] for project in recorded["projects"]] == ["alpha", "beta"]
    assert [
        {k: p[k] for k in ("login", "key", "expires", "revoked")} for p in recorded["persons"]
    ] == state.follow.reply["persons"]
    assert recorded["revoked"] == []
    assert host.invoke("org", "follow", data=b"") == 0
    assert json.loads(capsys.readouterr().out) == answer
    assert state.follow.fetches[1][state.follow.fetches[1].index("--since") + 1] == "a" * 40


def test_org_status_answers_the_applied_org_and_where_each_person_stands(org_host, capsys):
    """Prevent the interface from reading root's files, or taking a pending lock, a purge or a name for an admission."""
    host, state = org_host
    assert host.invoke("org", "status", data=b"") == 0
    assert json.loads(capsys.readouterr().out)["commit"] is None
    state.follow.reply["persons"].append(org_person("fay", ssh_key(95)))
    assert host.invoke("org", "follow", data=b"") == 0
    capsys.readouterr()
    host.write("/etc/porelo-host/people/cy.conf", f"member=alpha developer\nlocked=true\nssh={ssh_key(92)}\nexpires=\n")
    host.write(
        "/etc/porelo-host/people/di.conf",
        f"member=host-admin\nlocked=false\nssh={ssh_key(93)}\nexpires=\nlock=pending\n",
    )
    host.write("/etc/porelo-host/people/purged", "ann\n")
    before = {path: path.read_bytes() for path in host.root.rglob("*") if path.is_file()}
    assert host.invoke("org", "status", data=b"") == 0
    answer = json.loads(capsys.readouterr().out)
    assert answer == {
        "host": "host",
        "refused": None,
        "organization": "following",
        "commit": "a" * 40,
        "pinned": fingerprint(SIGNER_ONE),
        "projects": [
            {"project": name, "state": "waiting-for-token", "why": None, "since": "2026-10-30"}
            for name in ("alpha", "beta")
        ],
        "persons": [
            {
                "login": "alice",
                "state": "active",
                "host_admin": True,
                "projects": [{"project": "alpha", "role": "project-admin"}],
            },
            {"login": "ann", "state": "purged", "host_admin": False, "projects": []},
            {
                "login": "bob",
                "state": "active",
                "host_admin": False,
                "projects": [{"project": "beta", "role": "project-admin"}],
            },
            {
                "login": "cy",
                "state": "locked",
                "host_admin": False,
                "projects": [{"project": "alpha", "role": "developer"}],
            },
            {"login": "di", "state": "pending", "host_admin": True, "projects": []},
            {"login": "fay", "state": "named", "host_admin": False, "projects": []},
        ],
    }
    assert {path: path.read_bytes() for path in host.root.rglob("*") if path.is_file()} == before, "status wrote"


def test_org_status_is_roots_alone(org_host, capsys):
    """Prevent a person's sudo from reading where every other person stands."""
    host, _ = org_host
    assert host.invoke("org", "status", data=b"", sudo_user="alice") == 65
    assert "root's alone" in capsys.readouterr().err


def test_org_status_waits_for_a_writer_holding_the_hosts_lock(org_host, capsys):
    """Prevent the interface from reading a lock, a removal or a follow half done."""
    import fcntl
    import threading

    host, _ = org_host
    done = []
    with (host.root / "etc/porelo-host/forge.conf").open("rb") as mutex:
        fcntl.flock(mutex, fcntl.LOCK_EX)
        reader = threading.Thread(target=lambda: done.append(host.invoke("org", "status", data=b"")))
        reader.start()
        reader.join(0.5)
        assert done == [], "the reader did not wait for the lock"
    reader.join(10)
    assert done == [0]
    capsys.readouterr()


def test_follow_takes_the_first_organization_before_any_account_holds_it(org_host, capsys):
    """Prevent a fresh host from needing an admitted person's account before it can fetch its first organization."""
    host, state = org_host
    for user in ("alice", "bob"):
        host.accounts.pop(user)
        host.path(f"/etc/porelo-host/people/{user}.conf").unlink()
    assert host.invoke("org", "follow", data=b"") == 0
    assert [p["project"] for p in json.loads(capsys.readouterr().out)["projects"]] == ["alpha", "beta"]
    assert applied(host)["commit"] == "a" * 40
    assert "alice" in host.accounts and "bob" in host.accounts


def test_follow_retries_token_revocation_after_recording_the_revoked_key(org_host, capsys):
    """Prevent failed token deletion from losing key revocation or skipping deletion on the next follow."""
    host, state = org_host
    state.follow.reply["persons"][1]["revoked"] = True
    attempts = []

    def fail_once(name, values):
        if name == "forge_lock":
            assert "bob" in applied(host)["revoked"], "key revocation must precede remote token deletion"
            attempts.append(values)
            if len(attempts) == 1:
                raise host.factory.__globals__["Refusal"]("fixture API failure", 69)

    host.hook_inspect = fail_once
    assert host.invoke("org", "follow", data=b"") == 69
    assert capsys.readouterr().out == ""
    assert "bob" in applied(host)["revoked"]
    assert host.invoke("org", "follow", data=b"") == 0
    assert json.loads(capsys.readouterr().out)["commit"] == "a" * 40
    assert attempts == [("bob",), ("bob",), ("bob",)]
    assert "lock=pending" not in host.path("/etc/porelo-host/people/bob.conf").read_text()


@pytest.mark.parametrize(
    "stderr",
    [
        "porelo: hosts/host/card.yml at 1111111 is signed by SHA256:other, not the pinned host admin\n",
        "porelo: the organization at bbbbbbb does not descend from the applied aaaaaaa\n",
    ],
)
def test_follow_refuses_a_foreign_signer_or_an_older_or_forked_state_whole(org_host, capsys, stderr):
    """Prevent foreign signatures or replayed locks and handovers from changing host authority."""
    host, state = org_host
    assert host.invoke("org", "follow", data=b"") == 0
    capsys.readouterr()
    before = snapshot(host.path("/etc"))
    state.follow.reply["revision"] = "b" * 40
    state.follow.reply["persons"][1]["revoked"] = True
    state.follow.exit, state.follow.stderr = 65, stderr
    assert host.invoke("org", "follow", data=b"") == 65
    output = capsys.readouterr()
    assert not output.out
    assert output.err.startswith("porelo-host-person: ") and stderr.strip().removeprefix("porelo: ") in output.err
    assert state.follow.fetches[-1][state.follow.fetches[-1].index("--since") + 1] == "a" * 40
    now = snapshot(host.path("/etc"))
    for name in ("porelo-host/organization", "porelo-host/organization/refused.json"):
        before.pop(name, None)
        now.pop(name, None)
    assert now == before


def test_follow_reports_an_unfinished_removal_after_revoking_the_projects_access(org_host, capsys):
    """Prevent an unfinished forge removal from hiding retained work or keeping the departed membership active."""
    host, state = org_host
    assert host.invoke("org", "follow", data=b"") == 0
    capsys.readouterr()
    state.follow.reply["projects"] = state.follow.reply["projects"][:1]
    state.follow.reply["revision"] = "b" * 40
    assert host.invoke("org", "follow", data=b"") == 0
    answer = json.loads(capsys.readouterr().out)
    assert [p["project"] for p in answer["projects"]] == ["alpha", "beta"]
    assert answer["projects"][1]["state"] == "pending" and answer["projects"][1]["why"]
    assert host.path("/etc/porelo-host/projects/beta.conf").is_file()
    assert host.path("/etc/porelo-host/projects/alpha.conf").is_file()
    assert not host.path("/etc/porelo-host/organization/projects/beta.json").exists()
    assert "member=beta" not in host.path("/etc/porelo-host/people/bob.conf").read_text()


def test_org_pin_cannot_replace_the_setup_handover(org_host, capsys):
    """Prevent an obsolete command from replacing the setup's host admin keys."""
    host, state = org_host
    capsys.readouterr()
    pin = host.path("/etc/porelo-host/organization/pin")
    refused(host, capsys, 64, "org", "pin", "bob", SIGNER_TWO)
    assert pin.read_text() == f"alice {SIGNER_ONE}\n"
    assert stat.S_IMODE(pin.stat().st_mode) == 0o600
    assert state.follow.fetches == []


@pytest.mark.parametrize(
    "change, code",
    [
        ({"revision": "short"}, 65),
        ({"host_card": {"host": "other"}}, 65),
        ({"admins": []}, 65),
        ({"admins": None}, 65),
        ({"projects": {"alpha": "alice"}}, 65),
        ({"persons": None}, 65),
    ],
)
def test_follow_refuses_an_answer_of_another_shape_or_host_whole(org_host, capsys, change, code):
    """Prevent malformed answers, foreign hosts or missing admin keys from becoming host authority."""
    host, state = org_host
    before = snapshot(host.path("/etc"))
    state.follow.reply.update(change)
    assert host.invoke("org", "follow", data=b"") == code
    assert not capsys.readouterr().out
    assert not host.path("/etc/porelo-host/organization/applied.json").exists()
    assert snapshot(host.path("/etc")) == before


SUDOERS = ROOT / "roles/porelo/files/porelo-host-person.sudoers"


@pytest.mark.parametrize("caller", ["alice", "bob", ""])
def test_org_pin_through_sudo_is_refused(org_host, capsys, caller):
    """Prevent anyone reaching root through sudo, the pinned host admin too, from choosing the key the host trusts."""
    host, state = org_host
    capsys.readouterr()
    pin = host.path("/etc/porelo-host/organization/pin")
    pin.unlink()
    refused(host, capsys, 64, "org", "pin", "bob", SIGNER_TWO, data=b"", sudo_user=caller)
    assert not pin.exists()


def test_org_pin_by_a_non_root_caller_is_refused(org_host, capsys):
    """Prevent a caller who is not root from choosing the key the host anchors on."""
    host, state = org_host
    capsys.readouterr()
    pin = host.path("/etc/porelo-host/organization/pin")
    pin.unlink()
    host.euid = 1000
    refused(host, capsys, 69, "org", "pin", "bob", SIGNER_TWO, data=b"")
    assert not pin.exists()


@pytest.mark.parametrize(
    "args",
    [
        (),
        ("sync",),
        ("sync", "Alice"),
        ("sync", "-alpha"),
        ("sync", "alpha", "extra"),
        ("purge", "alice", "--force"),
        ("org", "extra"),
        ("org", "pin", "alice"),
        ("org", "pin", "Ada", ssh_key(100)),
        ("org", "pin", "alice", "ssh-ed25519 AAAA"),
    ],
)
def test_wrong_calls_cannot_change_the_host(host, capsys, args):
    """Prevent unintended privileged operations through malformed arguments."""
    refused(host, capsys, 64, *args)


def test_a_name_a_group_already_holds_is_no_new_persons(host, capsys):
    """Prevent organization admission from reusing an existing group or failing after account creation."""
    host.groups.add("operator")
    refused(host, capsys, 65, operation=lambda: host.admit("operator"), diagnostic="group")


@pytest.mark.parametrize("command", ["useradd", "usermod", "loginctl", "groupadd", "systemctl"])
def test_missing_dependencies_cannot_leave_a_partial_account(host, capsys, command):
    """Prevent discovering a missing required program after access or an account has been created."""
    host.commands.remove(command)
    refused(host, capsys, 69, operation=host.admit, diagnostic=command)


@pytest.mark.parametrize("verb", ["purge"])
def test_unknown_people_cannot_affect_unrelated_accounts(host, capsys, verb):
    """Prevent teardown verbs from disabling or deleting an account the helper does not manage."""
    host.accounts["alice"] = 1000
    refused(host, capsys, 65, verb, "alice", data=b"")


def test_a_purge_failing_after_the_vault_expires_the_account_again(host, capsys):
    """Prevent a failed purge from leaving a locked person's account unexpired, which a later lock would not redo."""
    assert host.admit() == 0
    assert host.revoke() == 0
    capsys.readouterr()
    host.calls.clear()
    host.fail = ["userdel"]
    assert host.invoke("purge", "alice", data=b"") == 69
    assert host.calls[-2:] == [
        ["usermod", "--expiredate", "1", "alice"],
        ["systemctl", "stop", "user@1000.service"],
    ], "the account left must be expired and its manager stopped"
    assert "locked=true" in host.path("/etc/porelo-host/people/alice.conf").read_text()


def test_purge_goes_on_when_logind_has_already_let_the_person_go(host, capsys):
    """Prevent a person without sessions or linger from making purge unfinishable."""
    assert host.admit() == 0
    assert host.revoke() == 0
    capsys.readouterr()
    # Disabling linger lets logind drop a person without a session, and terminate-user then knows nobody.
    host.fail = ["loginctl", "terminate-user"]
    host.calls.clear()
    assert host.invoke("purge", "alice", data=b"") == 0
    assert host.calls[-2:] == [["systemctl", "stop", "user@1000.service"], ["userdel", "--remove", "alice"]]


def test_lock_goes_on_when_logind_has_already_let_the_person_go(host, capsys):
    """Prevent a person without sessions or linger from making lock, and so purge, unfinishable."""
    assert host.admit() == 0
    capsys.readouterr()
    host.fail = ["loginctl", "terminate-user"]
    host.calls.clear()
    assert host.invoke("purge", "alice", data=b"") == 0
    assert ["usermod", "--lock", "--expiredate", "1", "alice"] in host.calls
    assert host.calls[-2:] == [["systemctl", "stop", "user@1000.service"], ["userdel", "--remove", "alice"]]


def test_purge_without_porelo_still_stops_the_lingering_user_manager(host, capsys):
    """Prevent userdel from refusing an account whose manager linger started, when Porelo is not installed."""
    assert host.admit() == 0
    host.commands.remove("porelo")
    host.calls.clear()
    assert host.invoke("purge", "alice", data=b"") == 0
    assert host.calls[-2:] == [["systemctl", "stop", "user@1000.service"], ["userdel", "--remove", "alice"]]


def test_people_are_told_from_system_accounts_by_the_hosts_own_uid_range(host, capsys):
    """Prevent a host with its own UID_MIN from having a service account treated as a person's."""
    host.write("/etc/login.defs", "# comment\nUID_MIN\t\t\t 2000\nUID_MAX 60000\n", 0o644)
    assert host.admit() == 0
    capsys.readouterr()
    host.accounts["alice"] = 1500
    refused(host, capsys, 65, "purge", "alice", data=b"")


def test_useradd_cannot_allocate_unplanned_subordinate_ranges(host):
    """Prevent useradd's configured defaults from colliding with the ranges reserved before admission."""
    assert host.admit() == 0
    creation = next(call for call in host.calls if call[0] == "useradd")
    assert "SUB_UID_COUNT=0" in creation and "SUB_GID_COUNT=0" in creation


def test_a_new_account_names_a_umask_without_group_write_ahead_of_usergroups(host):
    """Prevent USERGROUPS_ENAB's 002 from giving a person's directories group write, which Porelo then refuses."""
    assert host.admit() == 0
    creation = next(call for call in host.calls if call[0] == "useradd")
    assert creation[creation.index("--comment") + 1] == ",,,,umask=0022"


def test_admission_starts_the_persons_daemon_with_nothing_on_stdin(host, capsys):
    """Prevent the person's tunnel from reaching no porelod until they run setup themselves."""
    host.path("/run/user/1000").mkdir(parents=True)
    os.mknod(host.path("/run/user/1000/bus"), stat.S_IFSOCK | 0o600)
    given = {}
    run = host.run

    def recording(args, input=None):
        given[tuple(args)] = input
        return run(args, input)

    host.run = recording
    assert host.admit() == 0
    assert not capsys.readouterr().err
    start = host.calls.index(["systemctl", "start", "user@1000.service"])
    assert host.calls[start + 1] == as_alice(host, "setup")
    assert given[tuple(as_alice(host, "setup"))] == ""
    assert host.calls[start + 2] == [*as_alice(host)[:-1], "systemctl", "--user", "is-active", "--quiet", "porelod"]
    assert start > host.calls.index(["loginctl", "enable-linger", "alice"])


@pytest.mark.parametrize("missing", ["bus", "porelo", "running"])
def test_a_daemon_that_does_not_start_leaves_the_admission_standing(host, capsys, missing):
    """Prevent a missing bus, Porelo or a failing setup from taking back the access just given."""
    if missing != "bus":
        host.path("/run/user/1000").mkdir(parents=True)
        os.mknod(host.path("/run/user/1000/bus"), stat.S_IFSOCK | 0o600)
    if missing == "porelo":
        host.commands.remove("porelo")
    if missing == "running":
        host.fail = [*as_alice(host)[:-1], "systemctl", "--user", "is-active"]
    assert host.admit() == 0
    output = capsys.readouterr()
    assert not output.out
    assert "porelod of alice is not running" in output.err and "'porelo setup' as alice" in output.err
    assert "locked=false" in host.path("/etc/porelo-host/people/alice.conf").read_text()


def test_readmission_gives_an_older_account_the_umask_and_its_daemon(host, capsys):
    """Prevent a person admitted before either from keeping group write or a daemon nobody started."""
    host.path("/run/user/1000").mkdir(parents=True)
    os.mknod(host.path("/run/user/1000/bus"), stat.S_IFSOCK | 0o600)
    assert host.admit() == 0
    capsys.readouterr()
    assert host.revoke() == 0
    host.calls.clear()
    assert host.admit() == 0
    assert not capsys.readouterr().err
    assert ["usermod", "--comment", ",,,,umask=0022", "alice"] in host.calls
    start = host.calls.index(["systemctl", "start", "user@1000.service"])
    assert host.calls[start + 1] == as_alice(host, "setup")


def test_a_daemon_start_without_a_checked_runuser_runs_none(host, capsys):
    """Prevent root from running a runuser the fixed path's check never saw, to start a person's daemon."""
    host.path("/run/user/1000").mkdir(parents=True)
    os.mknod(host.path("/run/user/1000/bus"), stat.S_IFSOCK | 0o600)
    host.commands.remove("runuser")
    assert host.admit() == 0
    assert "runuser is missing" in capsys.readouterr().err
    assert not any(call[0] == "runuser" for call in host.calls)


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
    refused(host, capsys, 69, operation=host.admit)


def test_existing_people_group_and_missing_virtualization_groups_need_no_creation(host):
    """Prevent adding people to unavailable groups or recreating a group that already controls sudo access."""
    host.groups = {"porelo-people"}
    host.commands.remove("groupadd")
    assert host.admit() == 0
    assert not any(args[0] == "groupadd" for args in host.calls)
    assert ["usermod", "--append", "--groups", "porelo-people", "alice"] in host.calls


def test_a_record_never_authorizes_root_or_a_system_uid(host, capsys):
    """Prevent a stale admission record from authorizing modifications to a reassigned system account."""
    assert host.admit() == 0
    capsys.readouterr()
    host.accounts["alice"] = 999
    refused(host, capsys, 65, "purge", "alice", data=b"")


@pytest.mark.parametrize(
    "verb,missing",
    [("lock", "systemctl"), ("lock", "usermod"), ("lock", "runuser"), ("purge", "userdel"), ("purge", "runuser")],
)
def test_teardown_dependencies_are_checked_before_removing_access(host, capsys, verb, missing):
    """Prevent missing teardown programs from causing partial revocation or account loss."""
    assert host.admit() == 0
    capsys.readouterr()
    host.commands.remove(missing)
    if verb == "purge":
        refused(host, capsys, 69, verb, "alice", data=b"")
    else:
        host.calls.clear()
        assert host.revoke() == 69
        assert missing in capsys.readouterr().err
        assert not host.path("/etc/ssh/authorized_keys/alice").exists()
        assert ["gpasswd", "--delete", "alice", "porelo-people"] in host.calls
        assert not any(args[0] == missing for args in host.calls)


def test_failed_manager_stop_still_disables_the_account_and_allows_retry(host, capsys):
    """Prevent a manager failure from leaving SSH sessions enabled or being hidden by a completed lock."""
    assert host.admit() == 0
    capsys.readouterr()
    host.calls.clear()
    host.fail = ["systemctl", "stop"]
    assert host.revoke() == 69
    assert ["usermod", "--lock", "--expiredate", "1", "alice"] in host.calls
    assert "lock=pending" in host.path("/etc/porelo-host/people/alice.conf").read_text()
    assert not host.path("/etc/ssh/authorized_keys/alice").exists()
    assert not capsys.readouterr().out
    host.fail = None
    assert host.revoke() == 0
    assert "locked=true" in host.path("/etc/porelo-host/people/alice.conf").read_text()


def test_purge_can_finish_after_userdel_succeeded_in_an_interrupted_run(host, capsys):
    """Prevent a completed account deletion from making the remaining record and subordinate IDs unremovable."""
    assert host.admit() == 0
    assert host.revoke() == 0
    capsys.readouterr()
    del host.accounts["alice"]
    host.calls.clear()
    assert host.invoke("purge", "alice", data=b"") == 0
    assert host.calls == [["gpasswd", "--delete", "alice", "porelo-people"]]
    assert not host.path("/etc/porelo-host/people/alice.conf").exists()


def test_person_cannot_prevent_lock_by_changing_the_return_directory_mode(host, capsys):
    """Prevent a person's writable runtime directory mode from defeating host revocation."""
    assert host.admit() == 0
    capsys.readouterr()
    directory = host.path("/run/porelo-host/people/alice")
    directory.chmod(0o755)
    host.calls.clear()
    assert host.revoke() == 0
    assert not host.path("/etc/ssh/authorized_keys/alice").exists()
    assert not directory.exists()
    assert ["loginctl", "terminate-user", "alice"] in host.calls
    assert ["systemctl", "stop", "user@1000.service"] in host.calls


def test_install_restores_boot_rules_for_existing_admitted_people(host, capsys):
    """Prevent an upgrade or reboot from leaving recorded people without private return-socket directories."""
    assert host.admit() == 0
    capsys.readouterr()
    directory = host.path("/run/porelo-host/people/alice")
    (directory / "porelod.sock").unlink()
    directory.rmdir()
    rule = host.path("/etc/tmpfiles.d/porelo-person-alice.conf")
    rule.unlink()
    assert host.invoke("restore-runtime", data=b"") == 0
    assert json.loads(capsys.readouterr().out) == {"changed": 1}
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    uid = directory.stat().st_uid
    assert rule.read_text() == (
        "d /run/porelo-host/people/alice 0700 alice alice -\n"
        f"L /run/porelo-host/people/alice/porelod.sock - - - - /run/user/{uid}/porelo/porelod.sock\n"
    )
    assert os.readlink(directory / "porelod.sock") == f"/run/user/{uid}/porelo/porelod.sock"
    before = snapshot(host.root)
    assert host.invoke("restore-runtime", data=b"") == 0
    assert json.loads(capsys.readouterr().out) == {"changed": 0}
    assert snapshot(host.root) == before


def test_the_daemon_link_is_made_again_and_a_persons_own_entry_there_stays(host, capsys):
    """Prevent a tunnel without its fixed daemon name after a restore, and root replacing what the person put there."""
    assert host.admit() == 0
    capsys.readouterr()
    link = host.path("/run/porelo-host/people/alice/porelod.sock")
    link.unlink()
    assert host.invoke("restore-runtime", data=b"") == 0
    assert json.loads(capsys.readouterr().out) == {"changed": 1}
    uid = link.parent.stat().st_uid
    assert os.readlink(link) == f"/run/user/{uid}/porelo/porelod.sock"
    link.unlink()
    link.write_text("the person's own")
    assert host.invoke("restore-runtime", data=b"") == 0
    assert json.loads(capsys.readouterr().out) == {"changed": 0}
    assert not link.is_symlink() and link.read_text() == "the person's own"
    link.unlink()
    link.symlink_to("nowhere")  # The person's own link, dangling.
    assert host.invoke("restore-runtime", data=b"") == 0
    assert json.loads(capsys.readouterr().out) == {"changed": 0}
    assert os.readlink(link) == "nowhere"


def test_a_person_put_there_by_a_race_keeps_their_entry_and_admission_goes_on(host, capsys, monkeypatch):
    """Prevent a person's entry made between root's look and its link from failing a restore for everyone."""
    assert host.admit() == 0
    capsys.readouterr()
    link = host.path("/run/porelo-host/people/alice/porelod.sock")
    link.unlink()

    def raced(target, path):
        Path(path).write_text("the person's own")
        raise FileExistsError(path)

    monkeypatch.setattr(os, "symlink", raced)
    assert host.invoke("restore-runtime", data=b"") == 0
    capsys.readouterr()
    assert link.read_text() == "the person's own"


def test_follow_readmission_restores_the_persons_daemon_link(host, capsys):
    """Prevent a person from keeping no daemon name when the organization admits them again."""
    assert host.admit() == 0
    capsys.readouterr()
    link = host.path("/run/porelo-host/people/alice/porelod.sock")
    assert host.revoke() == 0
    assert host.admit() == 0
    capsys.readouterr()
    assert link.is_symlink()


def test_purge_expels_the_login_even_when_already_locked(host, capsys):
    """Prevent a prior lock from letting purge leave the person's and tasks' Matrix accounts active."""
    assert host.admit() == 0
    assert host.revoke() == 0
    host.events.clear()
    assert host.invoke("purge", "alice", data=b"") == 0
    capsys.readouterr()
    assert ["matrix_expel_revoke", "alice"] in host.events


def test_purge_keeps_the_locked_account_when_matrix_expulsion_fails(host, capsys):
    """Prevent account deletion from hiding a failed deactivation on the homeserver."""
    assert host.admit() == 0
    assert host.revoke() == 0
    capsys.readouterr()

    def unavailable(name, values):
        if name == "matrix_expel_revoke":
            raise host.factory.__globals__["Refusal"]("expulsion unavailable", 69)

    host.hook_inspect = unavailable
    host.calls.clear()
    assert host.invoke("purge", "alice", data=b"") == 69
    assert "expulsion unavailable" in capsys.readouterr().err
    assert "alice" in host.accounts
    assert host.path("/etc/porelo-host/people/alice.conf").exists()
    assert not any(call[0] == "userdel" for call in host.calls)
    assert ["usermod", "--lock", "--expiredate", "1", "alice"] in host.calls


@pytest.mark.parametrize("verb", ["lock", "purge"])
def test_teardown_removes_a_locked_persons_runtime_delivery_directory(host, capsys, monkeypatch, verb):
    """Prevent a completed or retried teardown from leaving the person's delivered credentials behind."""
    assert host.admit() == 0
    assert host.revoke() == 0
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
    assert (host.revoke() if verb == "lock" else host.invoke(verb, "alice", data=b"")) == 0
    assert not directory.exists()
    assert ("alice" not in host.accounts) == (verb == "purge")


def test_project_lock_removes_person_gate_and_agent_only_from_its_teams(follow_host, capsys):
    """Prevent a project lock from leaving task identities in any of its forge teams."""
    host, state = follow_host
    host.write(
        "/etc/porelo-host/people/carol.conf", f"member=beta developer\nlocked=false\nssh={ssh_key(2)}\nexpires=\n"
    )
    host.accounts["carol"] = 1200
    state.follow.reply["persons"].append(dict(org_person("carol", ssh_key(2)), expires=None))
    member = {"login": "carol", "role": "developer", "locked": False}
    state.follow.reply["projects"][0]["members"] = [member]
    state.follow.reply["projects"][1]["members"] = [dict(member)]
    assert host.invoke("org", "follow", data=b"") == 0
    capsys.readouterr()
    developers = state.teams["alpha"][1]["members"]
    assert set(developers) == {"carol", "porelo-carol", "codex-carol"}
    state.teams["alpha"].append({"id": 13, "name": "extra", "members": list(developers)})
    member["locked"] = True
    host.calls.clear()
    host.events.clear()
    assert host.invoke("org", "follow", data=b"") == 0
    assert state.teams["alpha"][1]["members"] == []
    assert state.teams["alpha"][2]["members"] == []
    assert set(state.teams["beta"][1]["members"]) == {"carol", "porelo-carol", "codex-carol"}
    assert not any(event[0] in ("forge_lock", "matrix_expel_revoke") for event in host.events)
    assert not any(
        "members" in call
        for call in host.calls
        if "/usr/libexec/porelo/transports/porelo-message-transport-matrix" in call
    )
    member["locked"] = False
    assert host.invoke("org", "follow", data=b"") == 0
    assert set(state.teams["alpha"][1]["members"]) == {"carol", "porelo-carol", "codex-carol"}


@pytest.mark.parametrize(
    "user,code",
    [
        ("root", 65),
        ("daemon", 65),
        ("existing", 65),
        ("Alice", 64),
        ("-alice", 64),
        ("../alice", 64),
        ("a" * 33, 64),
        ("a\n", 64),
    ],
)
def test_purge_cannot_target_root_system_or_unrecorded_accounts(host, capsys, user, code):
    """Prevent overwriting root, system accounts, unrelated accounts or paths outside the people directory."""
    host.accounts["existing"] = 1000
    refused(host, capsys, code, "purge", user)


@pytest.mark.parametrize(
    "file,change,code",
    [
        ("/etc/porelo-host/forge.conf", "missing", 69),
        ("/etc/porelo-host/forge.conf", "writable", 69),
        ("/etc/porelo-host/forge.conf", "link", 69),
        ("/etc/porelo-host", "writable", 69),
        ("/etc/ssh/authorized_keys/alice", "directory", 73),
        ("/etc/ssh/authorized_keys/alice", "link", 73),
        ("/etc/ssh/authorized_keys", "writable", 73),
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
    refused(host, capsys, code, operation=host.admit)


def test_purge_locks_first_clears_vault_then_removes_account_and_ranges(host, capsys):
    """Prevent deleting an active account or abandoning its vault and subordinate IDs."""
    assert host.admit() == 0
    host.write("/etc/subuid", "existing:100000:65536\nalice:165536:65536\nalice:400000:65536\n", 0o644)
    host.write("/etc/subgid", "existing:200000:65536\nalice:265536:65536\n", 0o644)
    host.calls.clear()
    capsys.readouterr()
    assert host.invoke("purge", "alice", data=b"") == 0
    assert json.loads(capsys.readouterr().out) == {"person": "alice", "purged": True}
    assert ["forge_drop_tokens", "alice", True] in host.events
    assert host.calls.index(["usermod", "--lock", "--expiredate", "1", "alice"]) < next(
        index for index, args in enumerate(host.calls) if args[0] == "runuser"
    )
    assert host.calls[-10:] == [
        # A locked account is expired, which PAM refuses to runuser and to the user manager; its password stays locked.
        ["usermod", "--expiredate", "", "alice"],
        ["systemctl", "start", "user@1000.service"],
        as_alice(host, "task", "stop", "--all"),
        as_alice(host, "vault", "clear", "--yes", "--force", "--json"),
        ["usermod", "--expiredate", "1", "alice"],
        ["systemctl", "stop", "user@1000.service"],
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
        "etc/porelo-host/organization/applied.json",
        "etc/porelo-host/people/purged",
        "etc/ssh/porelo-revoked.krl",
        "etc/subuid",
        "etc/subgid",
    }
    refused(host, capsys, 65, "purge", "alice", data=b"")


def test_missing_porelo_skips_only_its_optional_commands(host, capsys):
    """Prevent an absent Porelo binary from obstructing revocation or deleting a different program's data."""
    assert host.admit() == 0
    host.commands.remove("porelo")
    host.calls.clear()
    assert host.invoke("purge", "alice", data=b"") == 0
    assert not any(args[0] == "runuser" for args in host.calls)
    assert not host.path("/etc/porelo-host/people/alice.conf").exists()


def test_paths_owned_by_another_account_are_refused(host, capsys):
    """Prevent treating another account's directories or files as root's trusted configuration."""
    host.write("/etc/porelo-host/people/alice.conf", "bad-record\n")
    original = host.factory

    def wrong_owner(*args, **kwargs):
        kwargs["owner"] = os.getuid() + 1
        return original(*args, **kwargs)

    host.factory = wrong_owner
    refused(host, capsys, 69, "purge", "bob")


def test_purge_clears_no_vault_while_a_task_of_the_person_still_runs(host, capsys):
    """Prevent clearing a vault whose token a surviving task still holds, as Porelo's lock-out order says."""
    assert host.admit() == 0
    assert host.revoke() == 0
    capsys.readouterr()
    host.calls.clear()
    host.fail = as_alice(host, "task", "stop")
    assert host.invoke("purge", "alice", data=b"") == 69
    assert not any("vault" in args for args in host.calls)
    assert not any(args[0] == "userdel" for args in host.calls)
    assert host.calls[-2:] == [["usermod", "--expiredate", "1", "alice"], ["systemctl", "stop", "user@1000.service"]]
    assert "alice" in host.accounts
    assert host.path("/etc/porelo-host/people/alice.conf").exists()


def test_purge_goes_on_when_only_a_transport_could_not_clear_its_account(host, capsys):
    """Prevent a person whose project's transport cannot clear its account from staying unpurgeable for good."""
    assert host.admit() == 0
    capsys.readouterr()
    host.fail = as_alice(host, "vault", "clear")
    item = {"kind": "conversation", "what": "the matrix account of alpha", "status": "NOT_REMOVED", "why": "exit 78"}
    host.failed_output = json.dumps({"items": [item | {"transport": "matrix", "project": "alpha"}], "refused": False})
    assert host.invoke("purge", "alice", data=b"") == 0
    assert host.calls[-1] == ["userdel", "--remove", "alice"]


def test_purge_refuses_when_the_vault_kept_more_than_a_transports_account(host, capsys):
    """Prevent deleting the account while something of the vault other than a transport's account was not removed."""
    assert host.admit() == 0
    capsys.readouterr()
    host.fail = as_alice(host, "vault", "clear")
    item = {"kind": "vault", "what": "vault.bin", "status": "NOT_REMOVED", "why": "", "transport": "", "project": ""}
    host.failed_output = json.dumps({"items": [item], "refused": False})
    assert host.invoke("purge", "alice", data=b"") == 69
    assert not any(args[0] == "userdel" for args in host.calls)


@pytest.mark.parametrize(
    "answer",
    [
        {
            "items": [
                {"kind": "conversation", "status": "NOT_REMOVED", "transport": "matrix", "project": "alpha"},
                {"kind": "vault", "status": "NOT_REMOVED", "transport": "", "project": ""},
            ],
            "refused": False,
        },
        {"items": [{"kind": "conversation", "status": "NOT_REMOVED", "transport": "matrix"}], "refused": True},
        {"items": [], "refused": False},
    ],
    ids=["a-transport-and-the-vault-kept", "refused", "nothing-kept-yet-exit-1"],
)
def test_purge_refuses_unless_only_a_transports_account_was_kept(host, capsys, answer):
    """Prevent a transport's kept account from letting purge delete an account whose vault kept more."""
    assert host.admit() == 0
    capsys.readouterr()
    host.fail = as_alice(host, "vault", "clear")
    host.failed_output = json.dumps(answer)
    assert host.invoke("purge", "alice", data=b"") == 69
    assert not any(args[0] == "userdel" for args in host.calls)


def test_failed_vault_clear_keeps_the_locked_account_and_record_for_retry(host, capsys):
    """Prevent account deletion before the person's vault has been cleared successfully."""
    assert host.admit() == 0
    capsys.readouterr()
    host.calls.clear()
    host.fail = as_alice(host, "vault", "clear")
    assert host.invoke("purge", "alice", data=b"") == 69
    assert not any(args[0] == "userdel" for args in host.calls)
    assert host.calls[-2:] == [
        ["usermod", "--expiredate", "1", "alice"],
        ["systemctl", "stop", "user@1000.service"],
    ], "the account left must be expired and its manager stopped"
    assert "locked=true" in host.path("/etc/porelo-host/people/alice.conf").read_text()
    assert "alice" in host.accounts
    host.fail = None
    host.calls.clear()
    assert host.invoke("purge", "alice", data=b"") == 0
    assert not any(args[0] == "wg" for args in host.calls)
    assert not host.path("/etc/porelo-host/people/alice.conf").exists()


def test_failed_write_does_not_leave_a_record_or_staged_key_file(host, capsys):
    """Prevent a failed publication from reporting admission or leaving another copy of the key block."""

    def obstruct_after_validation(args):
        if args[0] == "useradd":
            host.path("/etc/ssh/authorized_keys").mkdir(parents=True, mode=0o755)
            host.path("/etc/ssh/authorized_keys/alice").mkdir()

    host.inspect = obstruct_after_validation
    assert host.admit() == 73
    output = capsys.readouterr()
    assert not output.out and "not a plain file" in output.err
    assert not list(host.root.rglob(".porelo-host-person.*"))
    assert "lock=pending" in host.path("/etc/porelo-host/people/alice.conf").read_text()
    assert not any(args[0] == "wg" and "allowed-ips" in args for args in host.calls)


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
    assert host.admit() == 69
    output = capsys.readouterr()
    assert not output.out and "ssh-keygen" in output.err
    assert "untrusted-token" not in output.err
    assert not host.path("/etc/porelo-host/people/alice.conf").exists()


@pytest.mark.parametrize("service", ["forge_lock"])
def test_failed_service_revocation_still_locks_the_host_account_for_retry(host, capsys, service):
    """Prevent a forge failure from leaving SSH sessions and the Linux login enabled."""
    assert host.admit() == 0
    capsys.readouterr()
    host.calls.clear()

    def unavailable(name, values):
        if name == service:
            raise host.factory.__globals__["Refusal"]("service unavailable", 69)

    host.hook_inspect = unavailable
    assert host.revoke() == 69
    assert ["usermod", "--lock", "--expiredate", "1", "alice"] in host.calls
    assert ["loginctl", "terminate-user", "alice"] in host.calls
    assert as_alice(host, "task", "stop", "--all") in host.calls
    assert "locked=true" in host.path("/etc/porelo-host/people/alice.conf").read_text()
    assert not capsys.readouterr().out


def test_follow_admits_a_new_card_without_inventing_legacy_agent_accounts(follow_host, capsys):
    """Prevent configured agent names from making new-person admission fail on nonexistent forge users."""
    host, state = follow_host
    state.follow.reply["persons"].append(dict(org_person("eve", ssh_key(4)), expires="2027-01-02"))
    state.follow.reply["projects"][0]["members"] = [{"login": "eve", "role": "developer", "locked": False}]
    assert host.invoke("org", "follow", data=b"") == 0
    assert set(state.teams["alpha"][1]["members"]) == {"eve", "porelo-eve"}
    assert host.path("/etc/ssh/authorized_keys/eve").read_text() == f'expiry-time="20270102000000Z" {ssh_key(4)}\n'
    assert "member=alpha developer" in host.path("/etc/porelo-host/people/eve.conf").read_text()


def test_follow_arms_the_projects_repositories_on_its_forge(follow_host, capsys):
    """Prevent a follow from leaving a carried repository's pushes unjudged."""
    host, state = follow_host
    state.follow.reply["projects"] = state.follow.reply["projects"][:1]
    assert host.invoke("org", "follow", data=b"") == 0
    armed = [
        args
        for args in host.calls
        if "podman" in args
        and args[args.index("podman") : args.index("podman") + 5] == ["podman", "exec", "forgejo", "sh", "-c"]
        and "pre-receive.d/porelo" in args[args.index("podman") + 5]
    ]
    assert [args[args.index("podman") + 7] for args in armed] == ["alpha"]


def test_people_can_reach_their_own_return_socket_directory(host):
    """Prevent a root-private parent hiding each person's own return-socket directory from them."""
    assert not host.path("/run/porelo-host").exists()
    assert host.admit() == 0
    for directory in ("/run/porelo-host", "/run/porelo-host/people"):
        assert host.path(directory).stat().st_mode & 0o777 == 0o755
    assert host.path("/run/porelo-host/people/alice").stat().st_mode & 0o777 == 0o700


def test_follow_uses_the_renewed_pin_file_with_the_accepted_commit(org_host, capsys):
    """Prevent the accepted state from overwriting the independently renewed trust pin."""
    host, state = org_host
    state.follow.reply["admins"] = [
        {"login": "bob", "key": SIGNER_TWO, "fingerprint": fingerprint(SIGNER_TWO), "backup": False}
    ]
    assert host.invoke("org", "follow", data=b"") == 0
    capsys.readouterr()
    pin = host.path("/etc/porelo-host/organization/pin")
    before = applied(host)
    assert host.invoke("org", "renew-pin", data=f"alice {SIGNER_ONE}\n".encode()) == 0
    capsys.readouterr()
    assert applied(host) == before
    state.follow.reply["revision"] = "b" * 40
    assert host.invoke("org", "follow", data=b"") == 0
    fetch = state.follow.fetches[-1]
    assert state.follow.pins[-1] == f"alice {SIGNER_ONE}\n"
    assert fetch[fetch.index("--since") + 1] == "a" * 40
    assert pin.read_text() == f"bob {SIGNER_TWO}\n"


def test_revocation_keeps_the_previous_org_key_when_the_card_changes(org_host, capsys):
    """Prevent replacing a revoked card from leaving its last organization key usable."""
    host, state = org_host
    state.follow.reply["persons"].append(org_person("carol", ssh_key(7)))
    assert host.invoke("org", "follow", data=b"") == 0
    capsys.readouterr()
    state.follow.reply["revision"] = "b" * 40
    state.follow.reply["persons"][-1] = org_person("carol", ssh_key(8), revoked=True)
    assert host.invoke("org", "follow", data=b"") == 0
    capsys.readouterr()
    for number in (7, 8):
        key = host.write("/etc/ssh/query-key", ssh_key(number) + "\n")
        result = subprocess.run(
            ["ssh-keygen", "-Q", "-f", str(host.path("/etc/ssh/porelo-revoked.krl")), str(key)],
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 1, f"revoked key {number} must remain in the KRL: {result.stdout}"


def test_failed_krl_publication_keeps_previous_org_keys_for_retry(org_host, capsys):
    """Prevent failed revocation publication from forgetting a replaced key on the next intake."""
    host, state = org_host
    state.follow.reply["persons"].append(org_person("carol", ssh_key(7)))
    assert host.invoke("org", "follow", data=b"") == 0
    capsys.readouterr()
    state.follow.reply["revision"] = "b" * 40
    state.follow.reply["persons"][-1] = org_person("carol", ssh_key(8), revoked=True)
    host.fail = ["ssh-keygen", "-q", "-k"]
    assert host.invoke("org", "follow", data=b"") == 69
    capsys.readouterr()
    host.fail = None
    assert host.invoke("org", "follow", data=b"") == 0
    capsys.readouterr()
    for number in (7, 8):
        key = host.write("/etc/ssh/query-key", ssh_key(number) + "\n")
        result = subprocess.run(
            ["ssh-keygen", "-Q", "-f", str(host.path("/etc/ssh/porelo-revoked.krl")), str(key)],
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 1, f"revoked key {number} must survive retry: {result.stdout}"


@pytest.mark.parametrize("arguments", [("add", "alice", "--role", "project-admin"), ("lock", "alice")])
def test_removed_person_verbs_are_unknown_and_change_nothing(host, capsys, arguments):
    """Prevent obsolete access verbs from bypassing the organization's authority or changing host state."""
    refused(host, capsys, 64, *arguments)
