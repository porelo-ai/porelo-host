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


@pytest.fixture
def host(tmp_path, monkeypatch):
    namespace = runpy.run_path(str(SCRIPT), run_name="person_unit_tests")
    h = Host(tmp_path, namespace["_test_entry"])
    monkeypatch.setattr(
        namespace["pwd"],
        "getpwnam",
        lambda user: SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid(), pw_dir=str(tmp_path / "home" / user)),
    )
    h.write("/etc/porelo-host/forge.conf", "address=10.73.7.1\n")
    h.write("/etc/subuid", "existing:100000:65536\n", 0o644)
    h.write("/etc/subgid", "existing:200000:65536\n", 0o644)
    h.write(
        "/etc/porelo-host/registry/applied.json",
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
    assert all(call[:2] == ["ssh-keygen", "-Q"] for call in host.calls), "refusal must precede changes"
    assert all(event[:2] == ["ssh-keygen", "-Q"] for event in host.events), "refusal must precede hooks"
    return output


def test_non_root_is_refused_before_reading_configuration_or_input(host, capsys):
    """Prevent an unprivileged invocation from reaching records or any account operation."""
    host.euid = 1000
    host.path("/etc/porelo-host/forge.conf").unlink()
    refused(host, capsys, 69, "add", "alice", "--role", "project-admin", data=b"\xff", diagnostic="root")


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


FORGE_ADMIN_TOKEN = "f" * 40


def fingerprint(key):
    blob = base64.b64decode(key.split(" ", 1)[1])
    return "SHA256:" + base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip("=")


@pytest.fixture
def sync_host(host, monkeypatch):
    scope = host.factory.__globals__
    host.commands.update({"systemd-run", "podman"})
    host.write(
        "/etc/porelo-host/forge.conf",
        "address=10.73.7.1\nport=3000\naccount=porelo-forge\nagents=codex\nname=forge.example.org\nhost=host\n",
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
        ("ada", "alpha", SIGNER_ONE, 90),
        ("bo", "beta", SIGNER_TWO, 91),
    ):
        host.accounts[admin] = 1000 + number
        host.write(
            f"/etc/porelo-host/people/{admin}.conf",
            f"member=hand\nmember={project} project-admin\nlocked=false\nssh={ssh_key(number)}\nexpires=\n",
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
                "persons": [],
                "admins": ["ada"],
                "transports": {},
            },
            "beta": {
                "project": "beta",
                "commit": "3" * 40,
                "access_commit": "4" * 40,
                "signer": SIGNER_TWO,
                "signers": [SIGNER_TWO],
                "persons": [],
                "admins": ["bo"],
                "transports": {},
            },
        },
        verify_exit=0,
        verify_stderr="",
        verify_calls=[],
        staged=None,
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
        if "podman" in args and args[-1] == "list":
            names = set(host.accounts) | {"porelo-" + user for user in host.accounts} | {"codex-alice"}
            text = "ID Username Email\n" + "".join(
                f"{number} {user} {user}@forge.example.org\n" for number, user in enumerate(sorted(names), 1)
            )
            return subprocess.CompletedProcess(args, 0, text, "")
        if args[0] == "systemd-run":
            host.calls.append(args)
            host.events.append(args)
            state.verify_calls.append(args)
            state.staged = sorted(p.name for p in host.path("/run/porelo-host/sync").iterdir())
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
            assert (url.scheme, url.hostname, url.port) == ("http", "localhost", None)
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
                    names = set(host.accounts) | {"porelo-" + user for user in host.accounts} | {"codex-alice"}
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
    host.write(
        "/etc/porelo-host/registry/applied.json",
        json.dumps(
            {
                "commit": "e" * 40,
                "host_card": {"host": "host", "signed_by": fingerprint(SIGNER_ONE)},
                "projects": [
                    {"name": "alpha", "admin": "ada", "access_repository": "alpha-access"},
                    {"name": "beta", "admin": "bo", "access_repository": "beta-access"},
                ],
                "persons": [],
                "revoked": [],
            }
        ),
    )
    host.calls.clear()
    host.events.clear()
    return host, state


def registry_person(login, key, revoked=False):
    return {"login": login, "ssh": key, "expires": "2027-10-30", "revoked": revoked}


@pytest.fixture
def registry_host(sync_host):
    """The sync host with ada pinned as host admin, her registry.bundle uploaded and nothing applied yet."""
    host, state = sync_host
    host.path("/etc/porelo-host/registry/applied.json").unlink()
    host.write("/etc/porelo-host/registry/pin.conf", f"admin=ada\nkey={SIGNER_ONE}\n")
    bundle = host.root / "home/ada/.local/share/porelo-host/setup/registry.bundle"
    bundle.write_bytes(b"registry")
    bundle.chmod(0o600)
    state.registry_reply = {
        "commit": "a" * 40,
        "host_card": {"host": "host", "signed_by": fingerprint(SIGNER_ONE)},
        "admins": ["ada"],
        "projects": [
            {"name": "alpha", "admin": "ada", "access_repository": "alpha-access"},
            {"name": "beta", "admin": "bo", "access_repository": "beta-access"},
        ],
        "persons": [registry_person("ada", SIGNER_ONE), registry_person("bo", SIGNER_TWO)],
    }
    state.registry_exit = 0
    state.registry_stderr = ""
    state.registry_calls = []
    sync_run = host.run

    def run(args, input=None):
        if args[0] == "systemd-run" and "registry" in args:
            host.calls.append(args)
            host.events.append(args)
            state.registry_calls.append(args)
            assert "--pipe" in args and "--wait" in args and "--quiet" in args and "--collect" in args
            assert "DynamicUser=yes" in args and "PrivateNetwork=yes" in args and "ProtectHome=yes" in args
            assert "--unit=porelo-host-registry" in args
            porelo = args[args.index("porelo") :]
            assert porelo[:3] == ["porelo", "registry", "verify"] and "--json" in porelo
            assert porelo[porelo.index("--repository") + 1] == (
                "/run/credentials/porelo-host-registry.service/registry.bundle"
            )
            assert porelo[porelo.index("--host") + 1] == "host"
            loaded = [arg.split(":", 1) for arg in args if arg.startswith("LoadCredential=")]
            assert len(loaded) == 1 and loaded[0][0] == "LoadCredential=registry.bundle"
            copied = Path(loaded[0][1])
            assert host.path("/run/porelo-host/sync") in copied.parents and not copied.is_symlink()
            assert copied.read_bytes() == b"registry"
            if state.registry_exit:
                return subprocess.CompletedProcess(args, state.registry_exit, "", state.registry_stderr)
            return subprocess.CompletedProcess(args, 0, json.dumps(state.registry_reply), "")
        return sync_run(args, input)

    host.run = run
    return host, state


def applied(host):
    path = host.path("/etc/porelo-host/registry/applied.json")
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    return json.loads(path.read_text())


def test_registry_applies_a_verified_bundle_against_the_pin_and_records_it_root_only(registry_host, capsys):
    """Prevent the host from taking projects or persons from anything but Porelo's verify of the pinned bundle."""
    host, state = registry_host
    capsys.readouterr()
    assert host.invoke("registry", data=b"", sudo_user="ada") == 0
    assert json.loads(capsys.readouterr().out) == {
        "commit": "a" * 40,
        "pinned": fingerprint(SIGNER_ONE),
        "projects": ["alpha", "beta"],
        "dropped": [],
        "revoked": [],
        "refused": [],
        "unchanged": False,
    }
    verify = state.registry_calls[0]
    assert verify[verify.index("--pinned") + 1] == fingerprint(SIGNER_ONE)
    assert "--since" not in verify
    recorded = applied(host)
    assert recorded["commit"] == "a" * 40
    assert [project["name"] for project in recorded["projects"]] == ["alpha", "beta"]
    assert recorded["persons"] == state.registry_reply["persons"]
    assert recorded["revoked"] == []
    assert list(host.path("/run/porelo-host/sync").iterdir()) == []

    assert host.invoke("registry", data=b"") == 0
    assert json.loads(capsys.readouterr().out)["unchanged"] is True
    assert state.registry_calls[1][state.registry_calls[1].index("--since") + 1] == "a" * 40


def test_registry_retries_token_revocation_after_recording_the_revoked_key(registry_host, capsys):
    """Prevent a failed token deletion from losing the key revocation or skipping deletion on the next intake."""
    host, state = registry_host
    state.registry_reply["persons"][1]["revoked"] = True
    attempts = []

    def fail_once(name, values):
        if name == "forge_lock":
            assert "bo" in applied(host)["revoked"], "key revocation must precede remote token deletion"
            attempts.append(values)
            if len(attempts) == 1:
                raise host.factory.__globals__["Refusal"]("fixture API failure", 69)

    host.hook_inspect = fail_once
    capsys.readouterr()
    assert host.invoke("registry", data=b"") == 69
    assert capsys.readouterr().out == ""
    assert "bo" in applied(host)["revoked"]
    assert host.invoke("registry", data=b"") == 0
    assert json.loads(capsys.readouterr().out)["unchanged"] is True
    assert attempts == [("bo",), ("bo",)]


@pytest.mark.parametrize(
    "stderr",
    [
        "porelo: hosts/host/card.yml at 1111111 is signed by SHA256:other, not the pinned host admin\n",
        "porelo: the registry at bbbbbbb does not descend from the applied aaaaaaa\n",
    ],
)
def test_registry_refuses_a_foreign_signer_or_an_older_or_forked_state_whole(registry_host, capsys, stderr):
    """Prevent a bundle signed by another key, or one rolling back a lock or handover, from changing anything."""
    host, state = registry_host
    capsys.readouterr()
    assert host.invoke("registry", data=b"") == 0
    capsys.readouterr()
    before_etc = snapshot(host.path("/etc"))
    state.registry_reply["commit"] = "b" * 40
    state.registry_reply["persons"][1]["revoked"] = True
    state.registry_exit = 65
    state.registry_stderr = stderr
    assert host.invoke("registry", data=b"", sudo_user="ada") == 65
    output = capsys.readouterr()
    assert not output.out
    assert output.err.startswith("porelo-host-person: ") and stderr.strip().removeprefix("porelo: ") in output.err
    assert state.registry_calls[-1][state.registry_calls[-1].index("--since") + 1] == "a" * 40
    assert snapshot(host.path("/etc")) == before_etc
    assert list(host.path("/run/porelo-host/sync").iterdir()) == []


def test_registry_names_a_dropped_project_keeps_it_and_its_sync_and_registration_are_refused(registry_host, capsys):
    """Prevent the host from removing a project on its own, or syncing one its registry no longer names."""
    host, state = registry_host
    capsys.readouterr()
    state.registry_reply["projects"] = [{"name": "alpha", "admin": "bo", "access_repository": "alpha-access"}]
    assert host.invoke("registry", data=b"") == 0
    answer = json.loads(capsys.readouterr().out)
    assert answer["projects"] == ["alpha"] and answer["dropped"] == ["alpha", "beta"]
    assert host.path("/etc/porelo-host/projects/beta.conf").is_file()
    assert host.path("/etc/porelo-host/projects/alpha.conf").is_file()
    for project, admin in (("beta", "bo"), ("alpha", "ada")):
        output = refused(host, capsys, 65, "sync", project, data=b"", sudo_user=admin)
        assert f"registry names no project {project} for {admin}" in output.err

    state.registry_reply["commit"] = "b" * 40
    state.registry_reply["projects"][0]["admin"] = "ada"
    assert host.invoke("registry", data=b"") == 0
    assert json.loads(capsys.readouterr().out)["dropped"] == ["beta"]
    assert host.invoke("sync", "alpha", data=b"", sudo_user="ada") == 0


def test_registry_refuses_a_readmitted_revoked_login_alone_while_a_lock_in_the_same_bundle_applies(
    registry_host, capsys
):
    """Prevent one refused entry from holding up a revocation, or an older card from undoing a purge."""
    host, state = registry_host
    capsys.readouterr()
    state.registry_reply["persons"].append(registry_person("cy", ssh_key(12), revoked=True))
    assert host.invoke("registry", data=b"") == 0
    assert json.loads(capsys.readouterr().out)["revoked"] == ["cy"]

    state.registry_reply["commit"] = "b" * 40
    state.registry_reply["persons"] = [
        registry_person("ada", SIGNER_ONE),
        registry_person("bo", SIGNER_TWO, revoked=True),
        registry_person("cy", ssh_key(13)),
        registry_person("Bad_Login", ssh_key(14)),
        {"login": "dan", "ssh": "ssh-ed25519 AAAA", "expires": None, "revoked": False},
        registry_person("ada", ssh_key(15)),
    ]
    state.registry_reply["projects"].append({"name": "Gamma!", "admin": "ada", "access_repository": "x"})
    assert host.invoke("registry", data=b"") == 0
    answer = json.loads(capsys.readouterr().out)
    assert answer["commit"] == "b" * 40
    assert answer["revoked"] == ["bo", "cy"]
    assert answer["projects"] == ["alpha"], "a revoked admin's project is named no more"
    assert len(answer["refused"]) == 6
    for named in ("cy", "Bad_Login", "dan", "ada", "Gamma!", "beta"):
        assert any(named in line for line in answer["refused"]), named
    assert all("ssh-ed25519" not in line for line in answer["refused"]), "a key never goes to output"
    recorded = applied(host)
    assert recorded["revoked"] == ["bo", "cy"]
    persons = {person["login"]: person for person in recorded["persons"]}
    assert set(persons) == {"ada", "bo", "cy"}
    assert persons["bo"]["revoked"] is True
    assert persons["cy"] == registry_person("cy", ssh_key(12), revoked=True), "the revoked entry stays as applied"
    assert persons["ada"] == registry_person("ada", SIGNER_ONE), "the first of a duplicated login applies alone"


def test_registry_handover_advances_the_pin_to_the_person_whose_key_signed_the_host_card(registry_host, capsys):
    """Prevent a verified handover from leaving the old host admin pinned, or an unnamed signer from taking the pin."""
    host, state = registry_host
    capsys.readouterr()
    before_etc = snapshot(host.path("/etc"))
    state.registry_reply["host_card"]["signed_by"] = fingerprint(ssh_key(77))
    assert host.invoke("registry", data=b"", sudo_user="ada") == 65
    output = capsys.readouterr()
    assert not output.out and "no person" in output.err
    assert snapshot(host.path("/etc")) == before_etc

    state.registry_reply["host_card"]["signed_by"] = fingerprint(SIGNER_TWO)
    assert host.invoke("registry", data=b"", sudo_user="ada") == 0
    assert json.loads(capsys.readouterr().out)["pinned"] == fingerprint(SIGNER_TWO)
    pin = host.path("/etc/porelo-host/registry/pin.conf")
    assert pin.read_text() == f"admin=bo\nkey={SIGNER_TWO}\n"
    assert stat.S_IMODE(pin.stat().st_mode) == 0o600

    refused(host, capsys, 65, "registry", data=b"", sudo_user="ada")
    bundle = host.root / "home/bo/.local/share/porelo-host/setup/registry.bundle"
    bundle.write_bytes(b"registry")
    bundle.chmod(0o600)
    state.registry_reply["commit"] = "b" * 40
    assert host.invoke("registry", data=b"", sudo_user="bo") == 0
    verify = state.registry_calls[-1]
    assert verify[verify.index("--pinned") + 1] == fingerprint(SIGNER_TWO)


def test_registry_pin_is_set_once_by_root_alone(registry_host, capsys):
    """Prevent anyone but root at setup from choosing the key the host anchors on, or a second pin replacing it."""
    host, state = registry_host
    capsys.readouterr()
    pin = host.path("/etc/porelo-host/registry/pin.conf")
    output = refused(host, capsys, 65, "registry", "pin", "bo", SIGNER_TWO)
    assert "pinned" in output.err
    pin.unlink()
    refused(host, capsys, 69, "registry", data=b"")
    assert host.invoke("registry", "pin", "ada", SIGNER_ONE, data=b"") == 0
    assert json.loads(capsys.readouterr().out) == {"admin": "ada", "pinned": fingerprint(SIGNER_ONE)}
    assert pin.read_text() == f"admin=ada\nkey={SIGNER_ONE}\n"
    assert stat.S_IMODE(pin.stat().st_mode) == 0o600
    assert state.registry_calls == []


def test_registry_by_sudo_allows_only_the_pinned_admin_and_their_own_plain_bundle(registry_host, capsys):
    """Prevent another person from bringing the host's registry, or root from reading a linked or writable bundle."""
    host, state = registry_host
    capsys.readouterr()
    for caller in ("bo", "ghost", ""):
        refused(host, capsys, 65, "registry", data=b"", sudo_user=caller)
    bundle = host.root / "home/ada/.local/share/porelo-host/setup/registry.bundle"
    bundle.chmod(0o620)
    assert host.invoke("registry", data=b"", sudo_user="ada") == 65
    bundle.chmod(0o600)
    bundle.unlink()
    bundle.symlink_to(host.root / "home/bo/.local/share/porelo-host/setup/beta/access.bundle")
    assert host.invoke("registry", data=b"", sudo_user="ada") == 65
    assert not capsys.readouterr().out
    assert state.registry_calls == []
    assert not host.path("/etc/porelo-host/registry/applied.json").exists()


@pytest.mark.parametrize(
    "change, code",
    [
        ({"commit": "short"}, 69),
        ({"host_card": {"host": "other", "signed_by": fingerprint(SIGNER_ONE)}}, 65),
        ({"host_card": {"host": "host"}}, 69),
        ({"host_card": {"host": "host", "signed_by": None}}, 69),
        ({"projects": {"alpha": "ada"}}, 69),
        ({"persons": None}, 69),
    ],
)
def test_registry_refuses_an_answer_of_another_shape_or_host_whole(registry_host, capsys, change, code):
    """Prevent a malformed answer, one for another host or one naming no signer from becoming the host's state."""
    host, state = registry_host
    capsys.readouterr()
    before_etc = snapshot(host.path("/etc"))
    state.registry_reply.update(change)
    assert host.invoke("registry", data=b"") == code
    assert not capsys.readouterr().out
    assert not host.path("/etc/porelo-host/registry/applied.json").exists()
    assert snapshot(host.path("/etc")) == before_etc


SUDOERS = ROOT / "roles/porelo/files/porelo-host-person.sudoers"


def test_registry_keeps_every_revocation_whatever_else_is_wrong_with_its_entry(registry_host, capsys):
    """Prevent a bad key, a bad expiry or a repeat from lifting a revocation, or a dropped revoked login its key."""
    host, state = registry_host
    capsys.readouterr()
    state.registry_reply["persons"] += [registry_person("cy", ssh_key(12)), registry_person("dan", ssh_key(13))]
    assert host.invoke("registry", data=b"") == 0
    assert json.loads(capsys.readouterr().out)["revoked"] == []

    state.registry_reply["commit"] = "b" * 40
    state.registry_reply["persons"] = [
        registry_person("ada", SIGNER_ONE),
        registry_person("bo", SIGNER_TWO),
        registry_person("bo", SIGNER_TWO, revoked=True),
        {"login": "cy", "ssh": "ssh-ed25519 AAAA", "expires": "2027-10-30", "revoked": True},
        {"login": "dan", "ssh": ssh_key(13), "expires": 7, "revoked": True},
        {"login": "eve", "ssh": "not a key", "expires": None, "revoked": True},
    ]
    assert host.invoke("registry", data=b"") == 0
    answer = json.loads(capsys.readouterr().out)
    assert answer["revoked"] == ["bo", "cy", "dan", "eve"]
    for named in ("bo", "cy", "dan", "eve"):
        assert any(named in line for line in answer["refused"]), named
    recorded = applied(host)
    assert recorded["revoked"] == ["bo", "cy", "dan", "eve"]
    persons = {person["login"]: person for person in recorded["persons"]}
    assert set(persons) == {"ada", "bo", "cy", "dan"}
    assert persons["bo"] == registry_person("bo", SIGNER_TWO, revoked=True)
    assert persons["cy"] == registry_person("cy", ssh_key(12), revoked=True), "the last applied key stays for the KRL"
    assert persons["dan"] == registry_person("dan", ssh_key(13), revoked=True)

    state.registry_reply["commit"] = "c" * 40
    state.registry_reply["persons"] = [registry_person("ada", SIGNER_ONE)]
    assert host.invoke("registry", data=b"") == 0
    assert json.loads(capsys.readouterr().out)["revoked"] == ["bo", "cy", "dan", "eve"]
    recorded = applied(host)
    assert recorded["revoked"] == ["bo", "cy", "dan", "eve"]
    assert {person["login"]: person for person in recorded["persons"]} == {
        "ada": registry_person("ada", SIGNER_ONE),
        "bo": registry_person("bo", SIGNER_TWO, revoked=True),
        "cy": registry_person("cy", ssh_key(12), revoked=True),
        "dan": registry_person("dan", ssh_key(13), revoked=True),
    }, "a revoked login dropped from the registry keeps its last applied entry"


def test_registry_names_no_project_for_a_revoked_admin_and_its_sync_is_refused(registry_host, capsys):
    """Prevent a revoked project admin from keeping a project the registry still lists for them, or syncing it."""
    host, state = registry_host
    capsys.readouterr()
    state.registry_reply["persons"][1]["revoked"] = True
    assert host.invoke("registry", data=b"") == 0
    answer = json.loads(capsys.readouterr().out)
    assert answer["projects"] == ["alpha"] and answer["dropped"] == ["beta"] and answer["revoked"] == ["bo"]
    assert any("beta" in line for line in answer["refused"])
    assert [project["name"] for project in applied(host)["projects"]] == ["alpha"]
    assert host.path("/etc/porelo-host/projects/beta.conf").is_file()
    for caller in ("bo", None):
        refused(host, capsys, 65, "sync", "beta", data=b"", sudo_user=caller)

    recorded = applied(host)
    recorded["projects"].append({"name": "beta", "admin": "bo", "access_repository": "beta-access"})
    host.write("/etc/porelo-host/registry/applied.json", json.dumps(recorded))
    for caller in ("bo", None):
        output = refused(host, capsys, 65, "sync", "beta", data=b"", sudo_user=caller)
        assert "bo" in output.err and "unlocked" in output.err


@pytest.mark.parametrize("barred", ["locked", "revoked", "unknown"])
def test_registry_by_sudo_is_refused_to_a_locked_revoked_or_unrecorded_pinned_admin(registry_host, capsys, barred):
    """Prevent a host admin the host has locked out or revoked from still bringing the host's registry."""
    host, state = registry_host
    capsys.readouterr()
    record = host.path("/etc/porelo-host/people/ada.conf")
    if barred == "locked":
        record.write_text(record.read_text().replace("locked=false", "locked=true"))
    elif barred == "unknown":
        record.unlink()
    else:
        host.write(
            "/etc/porelo-host/registry/applied.json",
            json.dumps(
                {
                    "commit": "e" * 40,
                    "host_card": {"host": "host", "signed_by": fingerprint(SIGNER_ONE)},
                    "projects": [],
                    "persons": [registry_person("ada", SIGNER_ONE, revoked=True)],
                    "revoked": ["ada"],
                }
            ),
        )
    output = refused(host, capsys, 65, "registry", data=b"", sudo_user="ada")
    assert "ada" in output.err
    assert state.registry_calls == []


@pytest.mark.parametrize("caller", ["ada", "bo", ""])
def test_registry_pin_through_sudo_is_refused(registry_host, capsys, caller):
    """Prevent anyone reaching root through sudo, the pinned host admin too, from choosing the key the host trusts."""
    host, state = registry_host
    capsys.readouterr()
    pin = host.path("/etc/porelo-host/registry/pin.conf")
    pin.unlink()
    refused(host, capsys, 65, "registry", "pin", "bo", SIGNER_TWO, data=b"", sudo_user=caller)
    assert not pin.exists()


def test_registry_pin_by_a_non_root_caller_is_refused(registry_host, capsys):
    """Prevent a caller who is not root from choosing the key the host anchors on."""
    host, state = registry_host
    capsys.readouterr()
    pin = host.path("/etc/porelo-host/registry/pin.conf")
    pin.unlink()
    host.euid = 1000
    refused(host, capsys, 69, "registry", "pin", "bo", SIGNER_TWO, data=b"")
    assert not pin.exists()


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
        ("registry", "extra"),
        ("registry", "pin", "ada"),
        ("registry", "pin", "Ada", ssh_key(100)),
        ("registry", "pin", "ada", "ssh-ed25519 AAAA"),
    ],
)
def test_wrong_calls_cannot_change_the_host(host, capsys, args):
    """Prevent unintended privileged operations through malformed arguments."""
    refused(host, capsys, 64, *args)


def test_a_name_a_group_already_holds_is_no_new_persons(host, capsys):
    """Prevent a person from being refused half-way by useradd, or put into a system group such as Ubuntu's operator."""
    host.groups.add("operator")
    refused(host, capsys, 65, "add", "operator", "--role", "project-admin", diagnostic="group")


@pytest.mark.parametrize("command", ["useradd", "usermod", "loginctl", "groupadd", "systemctl"])
def test_missing_dependencies_cannot_leave_a_partial_account(host, capsys, command):
    """Prevent discovering a missing required program after access or an account has been created."""
    host.commands.remove(command)
    refused(host, capsys, 69, "add", "alice", "--role", "project-admin", diagnostic=command)


@pytest.mark.parametrize("verb", ["lock", "purge"])
def test_unknown_people_cannot_affect_unrelated_accounts(host, capsys, verb):
    """Prevent teardown verbs from disabling or deleting an account the helper does not manage."""
    host.accounts["alice"] = 1000
    refused(host, capsys, 65, verb, "alice", data=b"")


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


def test_lock_goes_on_when_logind_has_already_let_the_person_go(host, capsys):
    """Prevent a person without sessions or linger from making lock, and so purge, unfinishable."""
    assert host.invoke("add", "alice", "--role", "project-admin") == 0
    capsys.readouterr()
    host.fail = ["loginctl", "terminate-user"]
    host.calls.clear()
    assert host.invoke("purge", "alice", data=b"") == 0
    assert ["usermod", "--lock", "--expiredate", "1", "alice"] in host.calls
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


def test_useradd_cannot_allocate_unplanned_subordinate_ranges(host):
    """Prevent useradd's configured defaults from colliding with the ranges reserved before admission."""
    assert host.invoke("add", "alice", "--role", "project-admin") == 0
    creation = next(call for call in host.calls if call[0] == "useradd")
    assert "SUB_UID_COUNT=0" in creation and "SUB_GID_COUNT=0" in creation


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
    [("lock", "systemctl"), ("lock", "usermod"), ("lock", "runuser"), ("purge", "userdel"), ("purge", "runuser")],
)
def test_teardown_dependencies_are_checked_before_removing_access(host, capsys, verb, missing):
    """Prevent missing teardown programs from causing partial revocation or account loss."""
    assert host.invoke("add", "alice", "--role", "project-admin") == 0
    capsys.readouterr()
    host.commands.remove(missing)
    if verb == "purge":
        refused(host, capsys, 69, verb, "alice", data=b"")
    else:
        host.calls.clear()
        assert host.invoke(verb, "alice", data=b"") == 69
        assert missing in capsys.readouterr().err
        assert not host.path("/etc/ssh/authorized_keys/alice").exists()
        assert ["gpasswd", "--delete", "alice", "porelo-people"] in host.calls
        assert not any(args[0] == missing for args in host.calls)


def test_failed_manager_stop_still_disables_the_account_and_allows_retry(host, capsys):
    """Prevent a VPN failure from leaving SSH sessions enabled or being hidden by an idempotent lock."""
    assert host.invoke("add", "alice", "--role", "project-admin") == 0
    capsys.readouterr()
    host.calls.clear()
    host.fail = ["systemctl", "stop"]
    assert host.invoke("lock", "alice", data=b"") == 69
    assert ["usermod", "--lock", "--expiredate", "1", "alice"] in host.calls
    assert "locked=true" in host.path("/etc/porelo-host/people/alice.conf").read_text()
    assert not host.path("/etc/ssh/authorized_keys/alice").exists()
    assert not capsys.readouterr().out
    host.fail = None
    assert host.invoke("lock", "alice", data=b"") == 0
    assert "locked=true" in host.path("/etc/porelo-host/people/alice.conf").read_text()


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
    assert host.calls == [["gpasswd", "--delete", "alice", "porelo-people"]]
    assert not host.path("/etc/porelo-host/people/alice.conf").exists()


def test_person_cannot_prevent_lock_by_changing_the_return_directory_mode(host, capsys):
    """Prevent a person's writable runtime directory mode from defeating host revocation."""
    assert host.invoke("add", "alice", "--role", "project-admin") == 0
    capsys.readouterr()
    directory = host.path("/run/porelo-host/people/alice")
    directory.chmod(0o755)
    host.calls.clear()
    assert host.invoke("lock", "alice", data=b"") == 0
    assert not host.path("/etc/ssh/authorized_keys/alice").exists()
    assert not directory.exists()
    assert ["loginctl", "terminate-user", "alice"] in host.calls
    assert ["systemctl", "stop", "user@1000.service"] in host.calls


def test_install_restores_boot_rules_for_existing_admitted_people(host, capsys):
    """Prevent an upgrade or reboot from leaving recorded people without private return-socket directories."""
    assert host.invoke("add", "alice", "--role", "project-admin") == 0
    capsys.readouterr()
    directory = host.path("/run/porelo-host/people/alice")
    directory.rmdir()
    rule = host.path("/etc/tmpfiles.d/porelo-person-alice.conf")
    rule.unlink()
    assert host.invoke("restore-runtime", data=b"") == 0
    assert json.loads(capsys.readouterr().out) == {"changed": 1}
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert rule.read_text() == "d /run/porelo-host/people/alice 0700 alice alice -\n"
    before = snapshot(host.root)
    assert host.invoke("restore-runtime", data=b"") == 0
    assert json.loads(capsys.readouterr().out) == {"changed": 0}
    assert snapshot(host.root) == before


def test_purge_expels_the_login_even_when_already_locked(host, capsys):
    """Prevent a prior lock from letting purge leave the person's and tasks' Matrix accounts active."""
    assert host.invoke("add", "alice", "--role", "project-admin") == 0
    assert host.invoke("lock", "alice", data=b"") == 0
    host.events.clear()
    assert host.invoke("purge", "alice", data=b"") == 0
    capsys.readouterr()
    assert ["matrix_expel_revoke", "alice"] in host.events


def test_purge_keeps_the_locked_account_when_matrix_expulsion_fails(host, capsys):
    """Prevent account deletion from hiding a failed deactivation on the homeserver."""
    assert host.invoke("add", "alice", "--role", "project-admin") == 0
    assert host.invoke("lock", "alice", data=b"") == 0
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


def test_project_lock_removes_person_gate_and_agent_only_from_its_teams(sync_host, capsys):
    """Prevent a project lock from leaving task identities in any of its forge teams."""
    host, state = sync_host
    host.write(
        "/etc/porelo-host/people/alice.conf", f"member=beta developer\nlocked=false\nssh={ssh_key(2)}\nexpires=\n"
    )
    host.accounts["alice"] = 1200
    person = {
        "login": "alice",
        "ssh": ssh_key(2),
        "expires": None,
        "revoked": False,
        "role": "developer",
        "hosts": ["host"],
        "locked": False,
    }
    state.verify_reply["alpha"]["persons"] = [person]
    applied = host.path("/etc/porelo-host/registry/applied.json")
    registry = json.loads(applied.read_text())
    registry["persons"].append(dict(registry_person("alice", ssh_key(2)), expires=None))
    applied.write_text(json.dumps(registry))
    assert host.invoke("sync", "alpha", data=b"") == 0
    capsys.readouterr()
    developers = state.teams["alpha"][1]["members"]
    assert set(developers) == {"alice", "porelo-alice", "codex-alice"}
    state.teams["alpha"].append({"id": 13, "name": "extra", "members": list(developers)})
    state.teams["beta"][1]["members"] = list(developers)
    person["locked"] = True
    host.calls.clear()
    host.events.clear()
    assert host.invoke("sync", "alpha", data=b"") == 0
    assert state.teams["alpha"][1]["members"] == []
    assert state.teams["alpha"][2]["members"] == []
    assert set(state.teams["beta"][1]["members"]) == {"alice", "porelo-alice", "codex-alice"}
    assert not any(event[0] in ("forge_lock", "matrix_expel_revoke") for event in host.events)
    transport = [
        call for call in host.calls if "/usr/libexec/porelo/transports/porelo-message-transport-matrix" in call
    ]
    assert transport[-1][-3:] == ["/usr/libexec/porelo/transports/porelo-message-transport-matrix", "members", "alpha"]
    person["locked"] = False
    assert host.invoke("sync", "alpha", data=b"") == 0
    assert set(state.teams["alpha"][1]["members"]) == {"alice", "porelo-alice", "codex-alice"}


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
def test_account_names_cannot_take_over_an_existing_account(host, capsys, user, code):
    """Prevent overwriting root, system accounts, unrelated accounts or paths outside the people directory."""
    host.accounts["existing"] = 1000
    refused(host, capsys, code, "add", user, "--role", "project-admin")


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
    refused(host, capsys, code, "add", "alice", "--role", "project-admin")


def test_purge_locks_first_clears_vault_then_removes_account_and_ranges(host, capsys):
    """Prevent deleting an active account or abandoning its vault and subordinate IDs."""
    assert host.invoke("add", "alice", "--role", "project-admin") == 0
    host.write("/etc/subuid", "existing:100000:65536\nalice:165536:65536\nalice:400000:65536\n", 0o644)
    host.write("/etc/subgid", "existing:200000:65536\nalice:265536:65536\n", 0o644)
    host.calls.clear()
    capsys.readouterr()
    assert host.invoke("purge", "alice", data=b"") == 0
    assert json.loads(capsys.readouterr().out) == {"person": "alice", "purged": True}
    assert host.calls.index(["usermod", "--lock", "--expiredate", "1", "alice"]) < next(
        index for index, args in enumerate(host.calls) if args[0] == "runuser"
    )
    assert host.calls[-8:] == [
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
            "--json",
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
        "etc/porelo-host/registry/applied.json",
        "etc/porelo-host/people/purged",
        "etc/ssh/porelo-revoked.krl",
        "etc/subuid",
        "etc/subgid",
    }
    refused(host, capsys, 65, "purge", "alice", data=b"")


def test_missing_porelo_skips_only_its_optional_commands(host, capsys):
    """Prevent an absent Porelo binary from obstructing revocation or deleting a different program's data."""
    assert host.invoke("add", "alice", "--role", "project-admin") == 0
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
    refused(host, capsys, 69, "add", "bob", "--role", "project-admin")


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
    assert host.calls[-2:] == [["usermod", "--expiredate", "1", "alice"], ["systemctl", "stop", "user@1000.service"]]
    assert "alice" in host.accounts
    assert host.path("/etc/porelo-host/people/alice.conf").exists()


def test_purge_goes_on_when_only_a_transport_could_not_clear_its_account(host, capsys):
    """Prevent a person whose project's transport cannot clear its account from staying unpurgeable for good."""
    assert host.invoke("add", "alice", "--role", "project-admin") == 0
    capsys.readouterr()
    host.fail = ["runuser", "-u", "alice", "--", "env", "XDG_RUNTIME_DIR=/run/user/1000", "porelo", "vault", "clear"]
    item = {"kind": "conversation", "what": "the matrix account of alpha", "status": "NOT_REMOVED", "why": "exit 78"}
    host.failed_output = json.dumps({"items": [item | {"transport": "matrix", "project": "alpha"}], "refused": False})
    assert host.invoke("purge", "alice", data=b"") == 0
    assert host.calls[-1] == ["userdel", "--remove", "alice"]


def test_purge_refuses_when_the_vault_kept_more_than_a_transports_account(host, capsys):
    """Prevent deleting the account while something of the vault other than a transport's account was not removed."""
    assert host.invoke("add", "alice", "--role", "project-admin") == 0
    capsys.readouterr()
    host.fail = ["runuser", "-u", "alice", "--", "env", "XDG_RUNTIME_DIR=/run/user/1000", "porelo", "vault", "clear"]
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
    assert host.invoke("add", "alice", "--role", "project-admin") == 0
    capsys.readouterr()
    host.fail = ["runuser", "-u", "alice", "--", "env", "XDG_RUNTIME_DIR=/run/user/1000", "porelo", "vault", "clear"]
    host.failed_output = json.dumps(answer)
    assert host.invoke("purge", "alice", data=b"") == 69
    assert not any(args[0] == "userdel" for args in host.calls)


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


def test_failed_write_does_not_leave_a_record_or_staged_key_file(host, capsys):
    """Prevent a failed publication from reporting admission or leaving another copy of the key block."""

    def obstruct_after_validation(args):
        if args[0] == "useradd":
            host.path("/etc/ssh/authorized_keys").mkdir(parents=True, mode=0o755)
            host.path("/etc/ssh/authorized_keys/alice").mkdir()

    host.inspect = obstruct_after_validation
    assert host.invoke("add", "alice", "--role", "project-admin") == 73
    output = capsys.readouterr()
    assert not output.out and "not a plain file" in output.err
    assert not list(host.root.rglob(".porelo-host-person.*"))
    assert "locked=true" in host.path("/etc/porelo-host/people/alice.conf").read_text()
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
    assert host.invoke("add", "alice", "--role", "project-admin") == 69
    output = capsys.readouterr()
    assert not output.out and "ssh-keygen" in output.err
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
    assert "locked=true" in host.path("/etc/porelo-host/people/alice.conf").read_text()
    assert not capsys.readouterr().out


def test_sync_admits_a_new_card_without_inventing_legacy_agent_accounts(sync_host, capsys):
    """Prevent configured legacy agent names from making new-person admission fail on nonexistent forge users."""
    host, state = sync_host
    state.verify_reply["alpha"]["persons"] = [
        {
            "login": "eve",
            "ssh": ssh_key(4),
            "expires": "2027-01-02",
            "revoked": False,
            "role": "developer",
            "hosts": ["host"],
            "locked": False,
        }
    ]
    applied = host.path("/etc/porelo-host/registry/applied.json")
    registry = json.loads(applied.read_text())
    registry["persons"].append(dict(registry_person("eve", ssh_key(4)), expires="2027-01-02"))
    applied.write_text(json.dumps(registry))
    assert host.invoke("sync", "alpha", data=b"") == 0
    assert set(state.teams["alpha"][1]["members"]) == {"eve", "porelo-eve"}
    assert host.path("/etc/ssh/authorized_keys/eve").read_text() == (f'expiry-time="20270102000000Z" {ssh_key(4)}\n')
    assert "member=alpha developer" in host.path("/etc/porelo-host/people/eve.conf").read_text()


def test_people_can_reach_their_own_return_socket_directory(host):
    """Prevent a root-private parent hiding each person's own return-socket directory from them."""
    assert not host.path("/run/porelo-host").exists()
    assert host.invoke("add", "alice", "--role", "project-admin") == 0
    for directory in ("/run/porelo-host", "/run/porelo-host/people"):
        assert host.path(directory).stat().st_mode & 0o777 == 0o755
    assert host.path("/run/porelo-host/people/alice").stat().st_mode & 0o777 == 0o700


def test_registry_passes_the_signer_it_saved_with_its_commit_after_an_interrupted_handover(registry_host, capsys):
    """Prevent a handover cut off between the record and the pin from making every later verify refuse the registry."""
    host, state = registry_host
    capsys.readouterr()
    state.registry_reply["host_card"]["signed_by"] = fingerprint(SIGNER_TWO)
    assert host.invoke("registry", data=b"", sudo_user="ada") == 0
    capsys.readouterr()
    pin = host.path("/etc/porelo-host/registry/pin.conf")
    pin.write_text(f"admin=ada\nkey={SIGNER_ONE}\n")
    state.registry_reply["commit"] = "b" * 40
    assert host.invoke("registry", data=b"", sudo_user="ada") == 0
    verify = state.registry_calls[-1]
    assert verify[verify.index("--pinned") + 1] == fingerprint(SIGNER_TWO)
    assert verify[verify.index("--since") + 1] == "a" * 40
    assert pin.read_text() == f"admin=bo\nkey={SIGNER_TWO}\n"


def test_revocation_keeps_the_previous_registry_key_when_the_card_changes(registry_host, capsys):
    """Prevent replacing a revoked card from leaving its last registry key usable."""
    host, state = registry_host
    state.registry_reply["persons"].append(registry_person("carol", ssh_key(7)))
    assert host.invoke("registry", data=b"") == 0
    capsys.readouterr()
    state.registry_reply["commit"] = "b" * 40
    state.registry_reply["persons"][-1] = registry_person("carol", ssh_key(8), revoked=True)
    assert host.invoke("registry", data=b"") == 0
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


def test_failed_krl_publication_keeps_previous_registry_keys_for_retry(registry_host, capsys):
    """Prevent failed revocation publication from forgetting a replaced key on the next intake."""
    host, state = registry_host
    state.registry_reply["persons"].append(registry_person("carol", ssh_key(7)))
    assert host.invoke("registry", data=b"") == 0
    capsys.readouterr()
    state.registry_reply["commit"] = "b" * 40
    state.registry_reply["persons"][-1] = registry_person("carol", ssh_key(8), revoked=True)
    host.fail = ["ssh-keygen", "-q", "-k"]
    assert host.invoke("registry", data=b"") == 69
    capsys.readouterr()
    host.fail = None
    assert host.invoke("registry", data=b"") == 0
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
