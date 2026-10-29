"""Guard credential delivery and revocation with isolated accounts and service replies."""

import io
import http.client
import json
import os
import runpy
import shutil
import ssl
import stat
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
import urllib.error
import urllib.request

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "roles/porelo/files/porelo-host-person"
ADMIN_TOKEN = "a" * 40
PERSON_TOKEN = "b" * 40
MATRIX_TOKEN = "fixture-machine-token"
MATRIX_ADMIN = "fixture-matrix-admin"
IDENTITIES = ["alice", "porelo-alice", "codex-alice", "claude-alice"]
REAL_CONTEXT = ssl.create_default_context
REAL_OPENER = urllib.request.build_opener
REAL_HTTPS = urllib.request.HTTPSHandler


class Services:
    def __init__(self, host):
        self.host = host
        self.calls = []
        self.inputs = []
        self.requests = []
        self.users = {}
        self.tokens = {}
        self.issue = {
            "machine": "host-alice",
            "token": MATRIX_TOKEN,
            "account": {"PORELO_MATRIX_ADMIN_TOKEN": MATRIX_ADMIN},
        }
        self.expulsion = {
            "machine": "host-alice",
            "known": True,
            "expelled": ["@person.host-alice:matrix.example.org"],
            "revoked": True,
        }
        self.transport_exit = 0
        self.transport_error = "machine was expelled; choose another machine name"
        self.failure = None
        self.api_failure = None
        self.bad_token_list = None
        self.limit = 1

    def run(self, args, input=None):
        self.calls.append(args)
        self.inputs.append(input)
        if self.failure:
            return subprocess.CompletedProcess(args, 1, self.failure, self.failure)
        assert isinstance(args, list)
        assert args[:2] == ["runuser", "-u"]
        assert args[3:5] == ["--", "env"]
        if "podman" in args:
            assert args[2] == "porelo-forge"
            assert "XDG_RUNTIME_DIR=/run/user/1200" in args
            assert input is None
            offset = args.index("podman")
            assert args[offset : offset + 6] == ["podman", "exec", "forgejo", "forgejo", "admin", "user"]
            action = args[offset + 6]
            if action == "list":
                answer = "ID Username Email IsActive IsAdmin\n" + "".join(
                    f"{n} {user} {user}@forge.example.org true false\n" for n, user in enumerate(self.users, 1)
                )
            else:
                user = args[args.index("--username") + 1]
                if action == "create":
                    assert "--random-password" in args
                    assert user not in self.users
                    self.users[user] = False
                    answer = "discarded-fixture-password"
                else:
                    assert action == "generate-access-token"
                    if user == "porelo-admin":
                        assert args[args.index("--scopes") + 1] == "write:admin"
                        answer = ADMIN_TOKEN + "\n"
                    else:
                        self.tokens.setdefault(user, []).append(len(self.tokens.get(user, [])) + 1)
                        answer = PERSON_TOKEN + "\n"
            return subprocess.CompletedProcess(args, 0, answer, "")
        if "/usr/libexec/porelo/transports/porelo-message-transport-matrix" in args:
            assert args[2] == "porelo-matrix"
            assert "XDG_RUNTIME_DIR=/run/user/1201" in args
            assert any(arg.startswith("HOME=") for arg in args)
            assert json.loads(input) in ({}, {"secrets": {"PORELO_MATRIX_ADMIN_TOKEN": MATRIX_ADMIN}})
            verb, machine = args[-2:]
            assert machine == "host-alice"
            if self.transport_exit:
                return subprocess.CompletedProcess(args, self.transport_exit, "", self.transport_error)
            answer = self.issue if verb == "issue" else self.expulsion
            return subprocess.CompletedProcess(args, 0, json.dumps(answer), "")
        assert args[2] == "alice"
        offset = args.index("/bin/sh")
        environment = dict(self.host.env)
        environment["HOME"] = str(self.host.home)
        return subprocess.run(args[offset:], input=input, text=True, capture_output=True, env=environment, check=False)

    def open(self, request, timeout):
        assert timeout == 30
        assert request.get_header("Authorization") == "token " + ADMIN_TOKEN
        url = urlsplit(request.full_url)
        assert (url.scheme, url.hostname, url.port) == ("https", "192.0.2.1", 3000)
        method, path = request.get_method(), url.path
        self.requests.append((method, path, request.data))
        user = path.split("/")[5]
        if self.api_failure and (isinstance(self.api_failure, int) or self.api_failure == user):
            code = self.api_failure if isinstance(self.api_failure, int) else 500
            raise urllib.error.HTTPError(request.full_url, code, "fixture failure", {}, io.BytesIO(b"secret"))
        assert user in IDENTITIES
        if method == "PATCH":
            assert json.loads(request.data)["prohibit_login"] is True
            self.users[user] = True
            data, status = {}, 200
        elif method == "DELETE":
            self.tokens[user].remove(int(path.rsplit("/", 1)[1]))
            data, status = None, 204
        else:
            assert method == "GET" and path.endswith("/tokens")
            page = int(parse_qs(url.query).get("page", [1])[0])
            items = self.tokens.get(user, [])
            data = [{"id": token, "name": "fixture"} for token in items[(page - 1) * self.limit : page * self.limit]]
            if self.bad_token_list is not None:
                data = self.bad_token_list
            status = 200
        response = io.BytesIO(json.dumps(data).encode())
        response.status = status
        return response


@pytest.fixture
def services(tmp_path, monkeypatch):
    namespace = runpy.run_path(str(SCRIPT), run_name="services_tests")
    scope = namespace["Host"].__init__.__globals__
    host = namespace["Host"]()
    host.root, host.owner, host.group = tmp_path, os.getuid(), os.getgid()
    host.commands = {"runuser", "podman", "/usr/libexec/porelo/transports/porelo-message-transport-matrix"}
    home = tmp_path / "home" / "alice"
    home.mkdir(parents=True)
    host.home, host.env = home, namespace["ENV"]
    entries = {
        "alice": SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid(), pw_dir=str(home)),
        "porelo-forge": SimpleNamespace(pw_uid=1200, pw_gid=1200, pw_dir=str(tmp_path / "home/forge")),
        "porelo-matrix": SimpleNamespace(pw_uid=1201, pw_gid=1201, pw_dir=str(tmp_path / "home/matrix")),
    }
    monkeypatch.setattr(scope["pwd"], "getpwnam", entries.__getitem__)
    config = host.path("/etc/porelo-host/forge.conf")
    config.parent.mkdir(parents=True, mode=0o700)
    config.write_text(
        "account=porelo-forge\nhost=host\nagents=codex,claude\n"
        "name=forge.example.org\nmatrix_name=matrix.example.org\naddress=192.0.2.1\nport=3000\n"
    )
    config.chmod(0o600)
    ca = host.path("/etc/porelo-host/forge/ca.pem")
    ca.parent.mkdir(mode=0o700)
    ca.write_text("fixture CA")
    ca.chmod(0o644)
    for directory in tmp_path.rglob("*"):
        if directory.is_dir():
            directory.chmod(0o755)
    recorder = Services(host)
    host.runner = recorder.run

    def context(*, cafile):
        assert cafile == str(ca)
        return ("CA", cafile)

    monkeypatch.setattr(scope["ssl"], "create_default_context", context)
    monkeypatch.setattr(scope["urllib"].request, "HTTPSHandler", lambda *, context: context)
    monkeypatch.setattr(scope["urllib"].request, "build_opener", lambda *handlers: recorder)
    return SimpleNamespace(host=host, recorder=recorder, scope=scope, entries=entries)


def hook(services, name, *args):
    return services.host.hooks[name](*args)


def token_file(services):
    return services.host.path("/run/porelo-host/people/alice/identities.tokens")


def machine_file(services):
    return services.host.home / ".config/porelo/matrix/host-registration-token"


def test_forge_admits_each_identity_once_and_delivers_only_private_tokens(services, capsys):
    """Prevent token rotation on retry and credentials reaching public output or other people."""
    hook(services, "forge_admit", "alice", [])
    assert list(services.recorder.users) == IDENTITIES
    path = token_file(services)
    assert path.read_text().splitlines() == [f"{user} {PERSON_TOKEN}" for user in IDENTITIES]
    assert (path.stat().st_uid, stat.S_IMODE(path.stat().st_mode)) == (os.getuid(), 0o600)
    assert (path.parent.stat().st_uid, stat.S_IMODE(path.parent.stat().st_mode)) == (os.getuid(), 0o700)
    assert stat.S_IMODE(path.parent.parent.stat().st_mode) == 0o755
    assert os.access(path.parent, os.W_OK), "the person must be able to unlink their imported tokens"
    before = path.stat().st_mtime_ns
    services.recorder.calls.clear()
    hook(services, "forge_admit", "alice", [])
    assert path.stat().st_mtime_ns == before
    assert not any("create" in call or "generate-access-token" in call for call in services.recorder.calls)
    path.unlink()
    hook(services, "forge_admit", "alice", [])
    assert not path.exists()
    assert capsys.readouterr() == ("", "")


def test_existing_forge_identities_receive_no_new_tokens(services):
    """Prevent overwriting a person's existing vault credentials when only some accounts are new."""
    services.recorder.users = {"alice": False, "codex-alice": False}
    hook(services, "forge_admit", "alice", [])
    assert token_file(services).read_text().splitlines() == [
        f"porelo-alice {PERSON_TOKEN}",
        f"claude-alice {PERSON_TOKEN}",
    ]


@pytest.mark.parametrize("config", [None, "host=host\nagents=\n", "account=\nhost=host\nagents=\n"])
def test_no_forge_account_means_no_forge_commands(services, config):
    """Keep admission and revocation usable on hosts with the forge switched off."""
    path = services.host.path("/etc/porelo-host/forge.conf")
    if config is None:
        path.unlink()
    else:
        path.write_text(config)
    hook(services, "forge_admit", "alice", [])
    hook(services, "forge_lock", "alice")
    assert services.recorder.calls == []


def test_forge_lock_disables_every_identity_and_deletes_every_token(services):
    """Prevent any login or older personal token from surviving a lock."""
    services.recorder.users = dict.fromkeys(IDENTITIES, False)
    services.recorder.tokens = {user: [1, 2, 3] for user in IDENTITIES}
    path = token_file(services)
    path.parent.mkdir(parents=True, mode=0o700)
    for directory in ("/run", "/run/porelo-host", "/run/porelo-host/people"):
        services.host.path(directory).chmod(0o755)
    path.write_text("fixture")
    path.chmod(0o600)
    hook(services, "forge_lock", "alice")
    assert services.recorder.users == dict.fromkeys(IDENTITIES, True)
    assert services.recorder.tokens == dict.fromkeys(IDENTITIES, [])
    assert not path.parent.exists()
    hook(services, "forge_lock", "alice")


def test_matrix_bootstrap_saves_admin_before_delivering_the_persons_token(services):
    """Prevent losing the homeserver admin credential or sending a token to the wrong account."""
    hook(services, "matrix_issue", "alice")
    admin = services.host.path("/etc/porelo-host/matrix-admin.token")
    assert admin.read_text().strip() == MATRIX_ADMIN
    assert stat.S_IMODE(admin.stat().st_mode) == 0o600
    assert machine_file(services).read_text() == MATRIX_TOKEN
    for path in [
        machine_file(services).parent,
        machine_file(services).parent.parent,
        services.host.home / ".config",
    ]:
        assert stat.S_IMODE(path.stat().st_mode) == 0o700
    assert stat.S_IMODE(machine_file(services).stat().st_mode) == 0o600
    assert json.loads(services.recorder.inputs[0]) == {}
    services.recorder.issue.pop("account")
    hook(services, "matrix_issue", "alice")
    assert json.loads(services.recorder.inputs[-2]) == {"secrets": {"PORELO_MATRIX_ADMIN_TOKEN": MATRIX_ADMIN}}
    for args in services.recorder.calls:
        assert not any(secret in " ".join(args) for secret in (MATRIX_TOKEN, MATRIX_ADMIN))


@pytest.mark.parametrize(
    "reply",
    [
        {"machine": "other", "token": MATRIX_TOKEN},
        {"machine": "host-alice"},
        [],
        {"machine": "host-alice", "token": "bad\ntoken"},
    ],
)
def test_matrix_refuses_wrong_machine_or_missing_or_invalid_tokens(services, reply):
    """Prevent a transport reply from registering a different machine or writing malformed credentials."""
    services.recorder.issue = reply
    with pytest.raises(services.scope["Refusal"]) as error:
        hook(services, "matrix_issue", "alice")
    assert error.value.code == 69
    assert not machine_file(services).exists()


def test_matrix_expelled_machine_reports_the_transport_refusal(services):
    """Prevent resurrecting a machine whose accounts were expelled."""
    services.recorder.transport_exit = 78
    with pytest.raises(services.scope["Refusal"]) as error:
        hook(services, "matrix_issue", "alice")
    assert error.value.code == 65
    assert str(error.value) == services.recorder.transport_error


@pytest.mark.parametrize("revoked", [True, False])
def test_matrix_expulsion_also_revokes_and_removes_the_local_token(services, revoked):
    """Prevent token revocation from leaving the machine's registered accounts or local credential active."""
    hook(services, "matrix_issue", "alice")
    services.recorder.calls.clear()
    services.recorder.expulsion["revoked"] = revoked
    hook(services, "matrix_expel_revoke", "alice")
    assert [args[-2:] for args in services.recorder.calls if "machine-token" in args] == [
        ["expel", "host-alice"],
    ]
    assert not machine_file(services).exists()


@pytest.mark.parametrize(
    "part",
    [".config", ".config/porelo", ".config/porelo/matrix", ".config/porelo/matrix/host-registration-token"],
)
def test_matrix_delivery_refuses_links_without_touching_the_destination(services, tmp_path, part):
    """Prevent an account-side link from directing a credential outside its private directory."""
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "host-registration-token"
    sentinel.write_text("untouched")
    path = services.host.home / part
    path.parent.mkdir(parents=True, exist_ok=True)
    path.symlink_to(sentinel if path.name == "host-registration-token" else outside)
    with pytest.raises(services.scope["Refusal"]) as error:
        hook(services, "matrix_issue", "alice")
    assert error.value.code == 73
    assert sentinel.read_text() == "untouched"
    assert services.host.path("/etc/porelo-host/matrix-admin.token").read_text().strip() == MATRIX_ADMIN


def test_service_failure_never_repeats_captured_secrets(services, capsys):
    """Prevent a failed secret-bearing command from echoing its stdout or stderr into a refusal."""
    services.recorder.failure = PERSON_TOKEN + MATRIX_ADMIN
    with pytest.raises(services.scope["Refusal"]) as error:
        hook(services, "forge_admit", "alice", [])
    assert error.value.code == 69
    assert PERSON_TOKEN not in str(error.value)
    assert MATRIX_ADMIN not in str(error.value)
    assert capsys.readouterr() == ("", "")


def test_forge_delivery_directory_is_traversable_with_a_private_root_umask(services):
    """Prevent a restrictive root umask from making the person's own delivered tokens unreachable."""
    previous = os.umask(0o077)
    try:
        hook(services, "forge_admit", "alice", [])
    finally:
        os.umask(previous)
    assert stat.S_IMODE(token_file(services).parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(token_file(services).parent.parent.stat().st_mode) == 0o755


def test_existing_private_runtime_directories_do_not_hide_the_persons_tokens(services):
    """Prevent a previously created root-only runtime directory from making delivered credentials unreadable."""
    path = token_file(services)
    path.parent.mkdir(parents=True, mode=0o700)
    for directory in (path.parent, path.parent.parent, path.parent.parent.parent, services.host.path("/run")):
        directory.chmod(0o700 if directory != services.host.path("/run") else 0o755)
    hook(services, "forge_admit", "alice", [])
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.parent.parent.stat().st_mode) == 0o755
    assert stat.S_IMODE(path.parent.parent.parent.stat().st_mode) == 0o755


@pytest.mark.parametrize("operation", ["forge_admit", "matrix_issue"])
def test_secrets_only_reach_their_designated_files_and_never_output(services, capsys, operation):
    """Prevent hidden copies of generated secrets in staged files, arguments or diagnostics."""
    hook(services, operation, "alice", *([[]] if operation == "forge_admit" else []))
    allowed = {token_file(services), machine_file(services), services.host.path("/etc/porelo-host/matrix-admin.token")}
    for path in services.host.root.rglob("*"):
        if path.is_file() and path not in allowed:
            data = path.read_bytes()
            for secret in (ADMIN_TOKEN, PERSON_TOKEN, MATRIX_TOKEN, MATRIX_ADMIN, "discarded-fixture-password"):
                assert secret.encode() not in data, f"a secret reached {path}"
    output = capsys.readouterr()
    for secret in (ADMIN_TOKEN, PERSON_TOKEN, MATRIX_TOKEN, MATRIX_ADMIN, "discarded-fixture-password"):
        assert secret not in output.out + output.err
        assert all(secret not in " ".join(args) for args in services.recorder.calls)


@pytest.mark.parametrize("change", ["link", "public", "writable", "wrong-owner"])
def test_untrusted_matrix_admin_credentials_never_reach_a_command(services, change, monkeypatch):
    """Prevent a forged or publicly readable homeserver admin credential from being used."""
    path = services.host.path("/etc/porelo-host/matrix-admin.token")
    path.write_text(MATRIX_ADMIN)
    path.chmod(0o600)
    if change == "link":
        path.unlink()
        path.symlink_to(services.host.path("/etc/porelo-host/forge.conf"))
    elif change in ("public", "writable"):
        path.chmod(0o644 if change == "public" else 0o622)
    else:
        real_lstat = Path.lstat

        def lstat(target, *args, **kwargs):
            status = real_lstat(target, *args, **kwargs)
            if target == path:
                return SimpleNamespace(st_uid=os.getuid() + 1, st_mode=status.st_mode)
            return status

        monkeypatch.setattr(Path, "lstat", lstat)
    with pytest.raises(services.scope["Refusal"]) as error:
        hook(services, "matrix_issue", "alice")
    assert error.value.code == 69
    assert services.recorder.calls == []


@pytest.mark.parametrize("value", ["../bad", "codex,", "codex,codex", "porelo", "codex\naccount=evil"])
def test_invalid_agent_lists_cannot_create_privileged_commands_or_duplicate_identities(services, value):
    """Prevent malformed forge configuration from creating unrelated identities or ambiguous tokens."""
    path = services.host.path("/etc/porelo-host/forge.conf")
    path.write_text(path.read_text().replace("agents=codex,claude", "agents=" + value))
    with pytest.raises(services.scope["Refusal"]):
        hook(services, "forge_admit", "alice", [])
    assert services.recorder.calls == []


def test_an_empty_agent_list_creates_only_the_person_and_gate(services):
    """Keep the forge usable without agent identities and avoid an empty agent's credential."""
    path = services.host.path("/etc/porelo-host/forge.conf")
    path.write_text(path.read_text().replace("agents=codex,claude", "agents="))
    hook(services, "forge_admit", "alice", [])
    assert list(services.recorder.users) == ["alice", "porelo-alice"]


def test_matrix_refusal_redacts_the_known_admin_token(services):
    """Prevent the expelled-machine diagnostic from exposing the supplied admin credential."""
    path = services.host.path("/etc/porelo-host/matrix-admin.token")
    path.write_text(MATRIX_ADMIN)
    path.chmod(0o600)
    services.recorder.transport_exit = 78
    services.recorder.transport_error = "expelled: " + MATRIX_ADMIN
    with pytest.raises(services.scope["Refusal"]) as error:
        hook(services, "matrix_issue", "alice")
    assert error.value.code == 65
    assert MATRIX_ADMIN not in str(error.value)


def test_matrix_revocation_stops_when_expulsion_fails(services):
    """Prevent an unsuccessful expulsion from being hidden by registration-token revocation."""
    services.recorder.transport_exit = 1
    with pytest.raises(services.scope["Refusal"]) as error:
        hook(services, "matrix_expel_revoke", "alice")
    assert error.value.code == 69
    assert [args[-2] for args in services.recorder.calls] == ["expel"]


def test_a_person_cannot_prevent_forge_lock_by_changing_their_token_file_mode(services):
    """Prevent a person from blocking remote revocation by making their delivery file public."""
    hook(services, "forge_admit", "alice", [])
    token_file(services).chmod(0o644)
    hook(services, "forge_lock", "alice")
    assert services.recorder.users == dict.fromkeys(IDENTITIES, True)
    assert not token_file(services).exists()


@pytest.mark.parametrize("target", ["directory-link", "foreign-directory", "file-link"])
def test_forge_delivery_refuses_links_and_another_accounts_directory(services, tmp_path, target):
    """Prevent root from delivering credentials through a link or into another person's directory."""
    path = token_file(services)
    path.parent.parent.mkdir(parents=True, mode=0o755)
    for directory in ("/run", "/run/porelo-host", "/run/porelo-host/people"):
        services.host.path(directory).chmod(0o755)
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "identities.tokens"
    sentinel.write_text("untouched")
    if target == "directory-link":
        path.parent.symlink_to(outside)
    else:
        path.parent.mkdir(mode=0o700)
        if target == "foreign-directory":
            services.entries["alice"].pw_uid = os.getuid() + 1
        else:
            path.symlink_to(sentinel)
    with pytest.raises(services.scope["Refusal"]) as error:
        hook(services, "forge_admit", "alice", [])
    assert error.value.code == 73
    assert services.recorder.calls == []
    assert sentinel.read_text() == "untouched"


def test_forge_cleanup_does_not_follow_links_or_remove_another_persons_directory(services):
    """Prevent root cleanup of a person's writable directory from deleting someone else's files."""
    hook(services, "forge_admit", "alice", [])
    path = token_file(services)
    other = path.parent.parent / "bob"
    other.mkdir(mode=0o700)
    sentinel = other / "identities.tokens"
    sentinel.write_text("untouched")
    (path.parent / "link").symlink_to(other)
    (path.parent / "extra").write_text("person's leftover file")
    hook(services, "forge_lock", "alice")
    assert not path.parent.exists()
    assert sentinel.read_text() == "untouched"


@pytest.mark.parametrize("target", ["directory-link", "foreign-directory"])
def test_forge_cleanup_refuses_a_link_or_another_persons_directory(services, tmp_path, target):
    """Prevent root cleanup from deleting a directory that is not the admitted person's own."""
    directory = token_file(services).parent
    directory.parent.mkdir(parents=True, mode=0o755)
    for parent in (directory.parent, directory.parent.parent, services.host.path("/run")):
        parent.chmod(0o755)
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "identities.tokens"
    sentinel.write_text("untouched")
    if target == "directory-link":
        directory.symlink_to(outside)
    else:
        directory.mkdir(mode=0o700)
        (directory / "identities.tokens").write_text("untouched")
        services.entries["alice"].pw_uid = os.getuid() + 1
    with pytest.raises(services.scope["Refusal"]) as error:
        services.host.remove_forge_tokens("alice")
    assert error.value.code == 73
    assert sentinel.read_text() == "untouched"
    assert (directory / "identities.tokens").read_text() == "untouched"


def test_failed_runtime_cleanup_still_revokes_forge_access_and_reports_the_leftover(services, monkeypatch):
    """Prevent failed cleanup of a person's writable directory from keeping forge identities enabled."""
    hook(services, "forge_admit", "alice", [])

    def occupied(path):
        raise OSError("directory still occupied")

    monkeypatch.setattr(services.scope["shutil"], "rmtree", occupied)
    occupied.avoids_symlink_attacks = True
    with pytest.raises(services.scope["Refusal"]) as error:
        hook(services, "forge_lock", "alice")
    assert error.value.code == 73
    assert services.recorder.users == dict.fromkeys(IDENTITIES, True)
    assert token_file(services).parent.exists()


def test_lock_treats_an_unknown_matrix_machine_as_already_revoked(services):
    """Prevent an already absent machine from blocking lock or retaining its local registration token."""
    hook(services, "matrix_issue", "alice")
    services.recorder.calls.clear()
    services.recorder.expulsion = {"machine": "host-alice", "known": False, "revoked": False, "expelled": []}
    hook(services, "matrix_expel_revoke", "alice")
    assert [args[-2:] for args in services.recorder.calls if "machine-token" in args] == [["expel", "host-alice"]]
    assert not machine_file(services).exists()


@pytest.mark.parametrize(
    "message", ["the homeserver refused expulsion", "the homeserver knows nothing of this machine"]
)
def test_every_matrix_refusal_blocks_lock_with_its_own_words(services, message):
    """Prevent a refusal, whatever its words, from being mistaken for an absent machine."""
    hook(services, "matrix_issue", "alice")
    services.recorder.transport_exit = 78
    services.recorder.transport_error = message
    with pytest.raises(services.scope["Refusal"]) as error:
        hook(services, "matrix_expel_revoke", "alice")
    assert error.value.code == 65
    assert str(error.value) == message
    assert machine_file(services).exists()


def test_issue_still_refuses_a_machine_the_homeserver_knows_nothing_of(services):
    """Prevent the lock-only unknown-machine exception from authorizing a failed admission."""
    services.recorder.transport_exit = 78
    services.recorder.transport_error = "the homeserver knows nothing of this machine"
    with pytest.raises(services.scope["Refusal"]) as error:
        hook(services, "matrix_issue", "alice")
    assert error.value.code == 65
    assert not machine_file(services).exists()


@pytest.mark.parametrize(
    "reply",
    [
        {"machine": "host-alice", "expelled": []},
        {"machine": "host-alice", "expelled": [], "revoked": "true"},
        {"machine": "host-alice", "expelled": "account", "revoked": True},
        {"machine": "host-alice", "expelled": [None], "revoked": True},
        {"machine": "host-alice", "expelled": [], "revoked": False},
        {"machine": "host-alice", "known": "false", "expelled": [], "revoked": False},
        {
            "machine": "host-alice",
            "known": False,
            "expelled": ["@person.host-alice:matrix.example.org"],
            "revoked": False,
        },
    ],
)
def test_invalid_expulsion_answers_cannot_report_completed_revocation(services, reply):
    """Prevent an incomplete or malformed expulsion result from hiding a failed revocation."""
    services.recorder.expulsion = reply
    with pytest.raises(services.scope["Refusal"]) as error:
        hook(services, "matrix_expel_revoke", "alice")
    assert error.value.code == 69


def test_command_runner_delivers_stdin_without_inheriting_caller_configuration(services):
    """Prevent credentials on arguments or inherited settings from reaching commands run by root."""
    result = services.scope["run_command"](
        [
            "/usr/bin/python3",
            "-I",
            "-c",
            "import os,sys; assert os.environ['PATH'] == sys.argv[1]; print(sys.stdin.read())",
            services.host.env["PATH"],
        ],
        input="fixture-secret",
    )
    assert result.returncode == 0
    assert result.stdout == "fixture-secret\n"
    assert result.stderr == ""


def test_forge_delivery_is_owned_by_the_person_before_publication(services, monkeypatch):
    """Prevent an atomic delivery from leaving the credential readable only by root or by another account."""
    services.entries["alice"].pw_uid = 2100
    services.entries["alice"].pw_gid = 2101
    changes = []
    directory_changes = []
    real_replace = os.replace

    def ownership(fd, uid, gid):
        changes.append((uid, gid))

    def directory_ownership(path, uid, gid):
        directory_changes.append((Path(path), uid, gid))

    def publish(source, destination):
        source = Path(source)
        assert source.parent == destination.parent
        assert stat.S_IMODE(source.stat().st_mode) == 0o600
        assert (2100, 2101) in changes
        assert (source.parent, 2100, 2101) in directory_changes
        real_replace(source, destination)

    monkeypatch.setattr(services.scope["os"], "fchown", ownership)
    monkeypatch.setattr(services.scope["os"], "chown", directory_ownership)
    monkeypatch.setattr(services.scope["os"], "replace", publish)
    hook(services, "forge_admit", "alice", [])
    assert token_file(services).read_text().splitlines() == [f"{user} {PERSON_TOKEN}" for user in IDENTITIES]


def test_forge_revocation_attempts_the_other_identities_when_one_fails(services):
    """Prevent one broken forge account from keeping the person's other identities enabled."""
    services.recorder.users = dict.fromkeys(IDENTITIES, False)
    services.recorder.api_failure = "alice"
    with pytest.raises(services.scope["Refusal"]):
        hook(services, "forge_lock", "alice")
    assert services.recorder.users == {"alice": False, **dict.fromkeys(IDENTITIES[1:], True)}


@pytest.mark.parametrize("reply", [{}, [{"id": "secret-token"}], [{"id": -1}], [{"id": True}], [{"id": 1}]])
def test_invalid_or_repeated_forge_token_pages_fail_without_a_loop(services, reply):
    """Prevent a bad API page from being treated as completed revocation or causing an endless lock."""
    services.recorder.users = dict.fromkeys(IDENTITIES, False)
    services.recorder.bad_token_list = reply
    with pytest.raises(services.scope["Refusal"]) as error:
        hook(services, "forge_lock", "alice")
    assert error.value.code == 69
    assert "secret-token" not in str(error.value)
    assert len(services.recorder.requests) <= 12


def test_admin_api_errors_do_not_echo_credentials_or_response_bodies(services):
    """Prevent failed revocation from disclosing the admin token or a server's sensitive response."""
    services.recorder.users = dict.fromkeys(IDENTITIES, False)
    services.recorder.api_failure = 403
    with pytest.raises(services.scope["Refusal"]) as error:
        hook(services, "forge_lock", "alice")
    assert error.value.code == 69
    assert "403" in str(error.value)
    assert "secret" not in str(error.value) and ADMIN_TOKEN not in str(error.value)


def test_a_malformed_http_reply_cannot_escape_with_sensitive_response_text(services, monkeypatch):
    """Prevent a broken HTTP status line from reaching stderr through an uncaught exception."""

    def broken(request, timeout):
        raise http.client.BadStatusLine(ADMIN_TOKEN)

    monkeypatch.setattr(services.recorder, "open", broken)
    with pytest.raises(services.scope["Refusal"]) as error:
        hook(services, "forge_lock", "alice")
    assert error.value.code == 69
    assert ADMIN_TOKEN not in str(error.value)


def test_admin_api_redirects_cannot_forward_an_admin_credential(services):
    """Prevent a forge redirect from copying the admin Authorization header to another service."""
    handler = services.scope["NoRedirect"]()
    assert handler.redirect_request(None, None, 302, "redirect", {}, "https://elsewhere.example.org") is None


@pytest.mark.parametrize("trusted_ca", [True, False])
def test_forge_lock_over_local_tls_checks_the_ca_and_revokes_tokens(services, tmp_path, monkeypatch, trusted_ca):
    """Exercise the real HTTP/TLS boundary so an untrusted server cannot accept the admin credential."""

    class Forge(BaseHTTPRequestHandler):
        def answer(self):
            request = urllib.request.Request(
                "https://192.0.2.1:3000" + self.path,
                data=self.rfile.read(int(self.headers["Content-Length"])) if self.command == "PATCH" else None,
                method=self.command,
                headers={"Authorization": self.headers["Authorization"]},
            )
            response = services.recorder.open(request, 30)
            self.send_response(response.status)
            self.end_headers()
            if response.status != 204:
                self.wfile.write(response.read())

        do_PATCH = do_GET = do_DELETE = answer

        def log_message(self, format, *args):
            pass

    try:
        server = HTTPServer(("127.0.0.1", 0), Forge)
    except PermissionError:
        pytest.skip("sandbox cannot bind a local TLS test server")
    try:
        openssl = shutil.which("openssl")
        if openssl is None:
            pytest.skip("openssl is not installed")
        for stem in ("server", "other"):
            made = subprocess.run(
                [
                    openssl,
                    "req",
                    "-x509",
                    "-newkey",
                    "ec",
                    "-pkeyopt",
                    "ec_paramgen_curve:P-256",
                    "-nodes",
                    "-keyout",
                    str(tmp_path / (stem + ".key")),
                    "-out",
                    str(tmp_path / (stem + ".pem")),
                    "-days",
                    "1",
                    "-subj",
                    "/CN=localhost",
                    "-addext",
                    "subjectAltName=IP:127.0.0.1",
                ],
                capture_output=True,
                text=True,
            )
            assert made.returncode == 0, made.stderr
        tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls.load_cert_chain(tmp_path / "server.pem", tmp_path / "server.key")
        server.socket = tls.wrap_socket(server.socket, server_side=True)
        ca = services.host.path("/etc/porelo-host/forge/ca.pem")
        ca.write_bytes((tmp_path / ("server.pem" if trusted_ca else "other.pem")).read_bytes())
        config = services.host.path("/etc/porelo-host/forge.conf")
        config.write_text(
            config.read_text().replace("192.0.2.1", "127.0.0.1").replace("port=3000", f"port={server.server_port}")
        )
        monkeypatch.setattr(ssl, "create_default_context", REAL_CONTEXT)
        monkeypatch.setattr(urllib.request, "build_opener", REAL_OPENER)
        monkeypatch.setattr(urllib.request, "HTTPSHandler", REAL_HTTPS)
        services.recorder.users = dict.fromkeys(IDENTITIES, False)
        services.recorder.tokens = {user: [1, 2] for user in IDENTITIES}
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            if trusted_ca:
                hook(services, "forge_lock", "alice")
                assert services.recorder.users == dict.fromkeys(IDENTITIES, True)
                assert services.recorder.tokens == dict.fromkeys(IDENTITIES, [])
            else:
                with pytest.raises(services.scope["Refusal"]) as error:
                    hook(services, "forge_lock", "alice")
                assert error.value.code == 69
                assert services.recorder.requests == []
        finally:
            server.shutdown()
            thread.join(timeout=5)
    finally:
        server.server_close()
