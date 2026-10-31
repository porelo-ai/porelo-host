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
# Admission makes the person's login and gate alone; the agents' identities only a 6j host has, and lock revokes them.
OWN = IDENTITIES[:2]
REAL_CONTEXT = ssl.create_default_context
REAL_OPENER = urllib.request.build_opener
REAL_HTTPS = urllib.request.HTTPSHandler


class Services:
    def __init__(self, host):
        self.scopes = {}
        self.host = host
        self.calls = []
        self.inputs = []
        self.requests = []
        self.users = {}
        self.tokens = {}
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
                        self.scopes[user] = args[args.index("--scopes") + 1]
                        answer = PERSON_TOKEN + "\n"
            return subprocess.CompletedProcess(args, 0, answer, "")
        if "/usr/libexec/porelo/transports/porelo-message-transport-matrix" in args:
            assert args[2] == "porelo-matrix"
            assert "XDG_RUNTIME_DIR=/run/user/1201" in args
            assert any(arg.startswith("HOME=") for arg in args)
            assert input is None
            assert args[-3:] == ["/usr/libexec/porelo/transports/porelo-message-transport-matrix", "expel", "alice"]
            return subprocess.CompletedProcess(args, self.transport_exit, "", self.transport_error)
        assert args[2] == "alice"
        offset = args.index("/bin/sh")
        environment = dict(self.host.env)
        environment["HOME"] = str(self.host.home)
        return subprocess.run(args[offset:], input=input, text=True, capture_output=True, env=environment, check=False)

    def open(self, request, timeout):
        assert timeout == 30
        assert request.get_header("Authorization") == "token " + ADMIN_TOKEN
        url = urlsplit(request.full_url)
        assert (url.scheme, url.hostname, url.port) == ("http", "localhost", None)
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
    host.commands = {"runuser", "env", "podman", "/usr/libexec/porelo/transports/porelo-message-transport-matrix"}
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


def test_forge_admits_each_identity_once_without_making_or_delivering_tokens(services, capsys):
    """Prevent admission from leaving credentials on disk or rotating a person's existing token."""
    hook(services, "forge_admit", "alice", [])
    assert list(services.recorder.users) == OWN
    assert not token_file(services).parent.exists()
    assert not any("generate-access-token" in call for call in services.recorder.calls)
    services.recorder.calls.clear()
    hook(services, "forge_admit", "alice", [])
    assert not any("create" in call or "generate-access-token" in call for call in services.recorder.calls)
    assert capsys.readouterr() == ("", "")


def test_existing_forge_identities_receive_no_new_tokens(services):
    """Prevent admission from replacing existing credentials when only some accounts are new."""
    services.recorder.users = {"alice": False, "codex-alice": False}
    hook(services, "forge_admit", "alice", [])
    assert set(services.recorder.users) == {"alice", "codex-alice", "porelo-alice"}
    assert not any("generate-access-token" in call for call in services.recorder.calls)
    assert not token_file(services).exists()


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
    hook(services, "forge_lock", "alice")
    assert services.recorder.users == dict.fromkeys(IDENTITIES, True)
    assert services.recorder.tokens == dict.fromkeys(IDENTITIES, [])
    hook(services, "forge_lock", "alice")


def test_service_failure_never_repeats_captured_secrets(services, capsys):
    """Prevent a failed secret-bearing command from echoing its stdout or stderr into a refusal."""
    services.recorder.failure = PERSON_TOKEN + MATRIX_ADMIN
    with pytest.raises(services.scope["Refusal"]) as error:
        hook(services, "forge_admit", "alice", [])
    assert error.value.code == 69
    assert PERSON_TOKEN not in str(error.value)
    assert MATRIX_ADMIN not in str(error.value)
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("operation", ["forge_admit"])
def test_secrets_only_reach_their_designated_files_and_never_output(services, capsys, operation):
    """Prevent hidden copies of generated secrets in staged files, arguments or diagnostics."""
    hook(services, operation, "alice", *([[]] if operation == "forge_admit" else []))
    allowed = {token_file(services)}
    for path in services.host.root.rglob("*"):
        if path.is_file() and path not in allowed:
            data = path.read_bytes()
            for secret in (ADMIN_TOKEN, PERSON_TOKEN, MATRIX_TOKEN, MATRIX_ADMIN, "discarded-fixture-password"):
                assert secret.encode() not in data, f"a secret reached {path}"
    output = capsys.readouterr()
    for secret in (ADMIN_TOKEN, PERSON_TOKEN, MATRIX_TOKEN, MATRIX_ADMIN, "discarded-fixture-password"):
        assert secret not in output.out + output.err
        assert all(secret not in " ".join(args) for args in services.recorder.calls)


@pytest.mark.parametrize("value", ["../bad", "codex,", "codex,codex", "porelo", "codex\naccount=evil"])
def test_invalid_agent_lists_cannot_revoke_unrelated_identities(services, value):
    """Prevent a malformed legacy agent list from naming other accounts for a lock to revoke."""
    path = services.host.path("/etc/porelo-host/forge.conf")
    path.write_text(path.read_text().replace("agents=codex,claude", "agents=" + value))
    with pytest.raises(services.scope["Refusal"]):
        hook(services, "forge_lock", "alice")
    assert services.recorder.calls == []


def test_admission_makes_no_agent_identity_whatever_forge_conf_names(services):
    """Porelo lends agents no forge identity of their own, so admission makes the person's login and gate alone."""
    hook(services, "forge_admit", "alice", [])
    assert list(services.recorder.users) == OWN
    assert not any("codex-alice" in str(call) or "claude-alice" in str(call) for call in services.recorder.calls)


def test_an_empty_agent_list_creates_only_the_person_and_gate(services):
    """Keep the forge usable without agent identities and avoid an empty agent's credential."""
    path = services.host.path("/etc/porelo-host/forge.conf")
    path.write_text(path.read_text().replace("agents=codex,claude", "agents="))
    hook(services, "forge_admit", "alice", [])
    assert list(services.recorder.users) == ["alice", "porelo-alice"]


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

    services.recorder.users = dict.fromkeys(OWN, False)
    monkeypatch.setattr(services.recorder, "open", broken)
    with pytest.raises(services.scope["Refusal"]) as error:
        hook(services, "forge_lock", "alice")
    assert error.value.code == 69
    assert ADMIN_TOKEN not in str(error.value)


def test_admin_api_redirects_cannot_forward_an_admin_credential(services):
    """Prevent a forge redirect from copying the admin Authorization header to another service."""
    handler = services.scope["NoRedirect"]()
    assert handler.redirect_request(None, None, 302, "redirect", {}, "https://elsewhere.example.org") is None


def test_forge_admin_transport_connects_only_to_the_private_socket(services, monkeypatch):
    """Keep revocation credentials off TCP while using HTTP request framing."""
    connected = []

    class Socket:
        def settimeout(self, timeout):
            pass

        def connect(self, endpoint):
            connected.append(endpoint)

    monkeypatch.setattr(services.scope["socket"], "socket", lambda family, kind: Socket())
    connection = services.scope["UnixConnection"]("/run/user/1200/porelo-forge/http.sock")
    connection.connect()
    assert connected == ["/run/user/1200/porelo-forge/http.sock"]


def test_matrix_expels_the_login_as_the_service_account_without_credentials(services):
    """Prevent purge leaving person and task accounts active or issuing a reusable host credential."""
    hook(services, "matrix_expel_revoke", "alice")
    assert len(services.recorder.calls) == 1
    assert services.recorder.calls[0][-3:] == [
        "/usr/libexec/porelo/transports/porelo-message-transport-matrix",
        "expel",
        "alice",
    ]
    assert services.recorder.inputs == [None]
    assert not services.host.path("/etc/porelo-host/matrix-admin.token").exists()


@pytest.mark.parametrize("code", [1, 78])
def test_failed_matrix_expulsion_blocks_removal_without_repeating_output(services, code):
    """Prevent a failed account deactivation from being treated as successful purge."""
    services.recorder.transport_exit = code
    services.recorder.transport_error = MATRIX_ADMIN
    with pytest.raises(services.scope["Refusal"]) as error:
        hook(services, "matrix_expel_revoke", "alice")
    assert error.value.code == 69
    assert MATRIX_ADMIN not in str(error.value)


def test_forge_admin_uses_only_the_private_socket_without_a_ca(services):
    """Keep administrative credentials off TCP and remove dependency on a forge CA."""
    services.host.path("/etc/porelo-host/forge/ca.pem").unlink()
    base, endpoint = services.host.forge_endpoint()
    assert base == "http://localhost/api/v1/admin/users/"
    assert str(endpoint).endswith("/run/user/1200/porelo-forge/http.sock")

    path = token_file(services)
    path.parent.mkdir(parents=True, mode=0o700)
    path.write_text("legacy fixture credential")
    for directory in ("/run", "/run/porelo-host", "/run/porelo-host/people"):
        services.host.path(directory).chmod(0o755)
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
    path = token_file(services)
    path.parent.mkdir(parents=True, mode=0o700)
    path.write_text("legacy fixture credential")
    for directory in ("/run", "/run/porelo-host", "/run/porelo-host/people"):
        services.host.path(directory).chmod(0o755)

    def occupied(path):
        raise OSError("directory still occupied")

    monkeypatch.setattr(services.scope["shutil"], "rmtree", occupied)
    occupied.avoids_symlink_attacks = True
    with pytest.raises(services.scope["Refusal"]) as error:
        hook(services, "forge_lock", "alice")
    assert error.value.code == 73
    assert services.recorder.users == dict.fromkeys(OWN, True)
    assert token_file(services).parent.exists()


def test_project_team_session_has_organization_scopes(services, monkeypatch):
    """Prevent Forgejo scope refusal from leaving project team access unreconciled."""
    scopes = []
    host = services.host
    monkeypatch.setattr(host, "forge_token", lambda account, user, scope, name: scopes.append(scope) or ADMIN_TOKEN)
    monkeypatch.setattr(host, "forge_drop_named", lambda *args: None)
    monkeypatch.setattr(host, "forge_pages", lambda *args: [])
    with pytest.raises(services.scope["Refusal"], match="Owners and developers"):
        host.forge_project_apply("alpha", "alice", {})
    assert set(scopes[0].split(",")) == {"write:admin", "write:organization", "read:user"}


def test_forge_unlock_patches_only_existing_identities(services, monkeypatch):
    """Prevent absent legacy agent accounts from interrupting membership restoration."""
    services.recorder.users = dict.fromkeys(OWN, True)
    patched = []

    def api(opener, base, token, method, identity, expected, data):
        assert identity in services.recorder.users
        patched.append(identity)

    monkeypatch.setattr(services.host, "forge_api", api)
    monkeypatch.setattr(services.host, "forge_drop_named", lambda *args: None)
    services.host.forge_unlock("alice")
    assert set(patched) == set(OWN)


def test_forge_team_pages_accept_existing_forge_login_characters(services, monkeypatch):
    """Prevent an unrelated valid Forgejo identity from blocking project access revocation."""
    rows = [{"login": "Alice_Q.dev"}]
    replies = iter([rows, []])
    monkeypatch.setattr(services.host, "forge_api", lambda *args: next(replies))
    assert services.host.forge_pages(None, "", ADMIN_TOKEN, "teams/1/members", "login") == rows


@pytest.mark.parametrize("linked", [False, True])
def test_missing_person_account_does_not_skip_forge_revocation(services, linked, tmp_path):
    """Prevent missing passwd entries or unsafe runtime paths from retaining Forgejo credentials."""
    host = services.host
    directory = token_file(services).parent
    host.directories(directory.parent)
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "keep"
    sentinel.write_text("untouched")
    if linked:
        directory.symlink_to(outside)
    else:
        directory.mkdir(mode=0o700)
        (directory / "leftover").write_text("runtime")
    services.entries.pop("alice")
    services.recorder.users = dict.fromkeys(IDENTITIES, False)
    services.recorder.tokens = {user: [1, 2] for user in IDENTITIES}
    if linked:
        with pytest.raises(services.scope["Refusal"]):
            host.forge_lock("alice")
        assert directory.is_symlink()
    else:
        host.targets("alice")
        host.forge_lock("alice")
        assert not directory.exists()
    assert services.recorder.users == dict.fromkeys(IDENTITIES, True)
    assert services.recorder.tokens == dict.fromkeys(IDENTITIES, [])
    assert sentinel.read_text() == "untouched"
