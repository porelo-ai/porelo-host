"""Exercise project registration against a TLS forge and removal against real Git histories."""

import base64
import errno
import fcntl
import http.client
import io
import json
import os
import runpy
import ssl
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

import pytest

from test_porelo_host_push import CENTRAL_TOKEN, assert_no_token_anywhere, bare, commit, git, host as push_host

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "roles/forge/files/porelo-host-project"
KEY_WIRE = b"\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20" + bytes(range(32))
KEY = "ssh-ed25519 " + base64.b64encode(KEY_WIRE).decode("ascii")
ADMIN_TOKEN = "a" * 40
PUBLISHER_TOKEN = "b" * 40


class Forge:
    def __init__(self):
        self.users = {"alice": {}, "bob": {}}
        self.organizations = {}
        self.teams = {}
        self.secrets = {}
        self.repositories = {}
        self.packages = {}
        self.calls = []
        self.failure = None
        self.redirect = False
        self.redirected = []
        self.pages = {}
        self.responses = {}
        self.queries = []

    def respond(self, method, url, body):
        parsed = urlsplit(url)
        self.queries.append((method, parsed.path, parsed.query))
        if (method, parsed.path) in self.responses:
            self.calls.append((method, parsed.path, body))
            return self.responses[(method, parsed.path)]
        page = int(parse_qs(parsed.query).get("page", ["1"])[0])
        if parsed.path in self.pages:
            self.calls.append((method, parsed.path, body))
            pages = self.pages[parsed.path]
            return 200, pages[min(page - 1, len(pages) - 1)]
        if page > 1:
            return 200, []
        return self.request(method, parsed.path, body)

    def request(self, method, path, body):
        self.calls.append((method, path, body))
        if self.failure == (method, path):
            return 503, {"message": ADMIN_TOKEN + PUBLISHER_TOKEN}
        parts = path.removeprefix("/api/v1/").split("/")
        if method == "GET":
            if parts[0] == "packages":
                return 200, self.packages.get(parts[1], [])
            if parts[0] == "users":
                return (200, self.users[parts[1]]) if parts[1] in self.users else (404, {})
            if parts[0] == "orgs":
                org = parts[1]
                if org not in self.organizations:
                    return 404, {}
                if len(parts) == 2:
                    return 200, self.organizations[org]
                if parts[2] == "teams":
                    return 200, [dict(id=key, **team) for key, team in self.teams.items() if team["org"] == org]
                if parts[2] == "repos":
                    return 200, self.repositories.get(org, [])
        if method == "POST" and parts[:2] == ["admin", "users"]:
            if len(parts) == 4 and parts[3] == "orgs":
                org = body["username"]
                self.organizations[org] = {"username": org}
                self.teams[len(self.teams) + 1] = {"org": org, "name": "Owners", "members": [parts[2]]}
                return 201, self.organizations[org]
        if method == "POST" and parts[0] == "orgs" and parts[2] == "teams":
            team_id = len(self.teams) + 1
            self.teams[team_id] = dict(body, org=parts[1], members=[])
            return 201, {"id": team_id, **body}
        if method == "PUT" and parts[0] == "teams" and parts[2] == "members":
            members = self.teams[int(parts[1])]["members"]
            if parts[3] not in members:
                members.append(parts[3])
            return 204, None
        if method == "PUT" and parts[0] == "orgs" and parts[2:4] == ["actions", "secrets"]:
            self.secrets[(parts[1], parts[4])] = body["data"]
            return 201, None
        if method == "DELETE" and parts[0] == "orgs":
            org = parts[1]
            if self.repositories.get(org) or self.packages.get(org):
                return 500, {"message": "the organization still owns repositories or packages"}
            del self.organizations[org]
            self.teams = {key: team for key, team in self.teams.items() if team["org"] != org}
            self.secrets = {key: value for key, value in self.secrets.items() if key[0] != org}
            self.repositories.pop(org, None)
            return 204, None
        if method == "DELETE" and parts[0] == "repos":
            self.repositories[parts[1]] = [repo for repo in self.repositories[parts[1]] if repo["name"] != parts[2]]
            return 204, None
        if method == "DELETE" and parts[0] == "packages":
            package_type, name, version = map(unquote, parts[2:])
            self.packages[parts[1]] = [
                package
                for package in self.packages[parts[1]]
                if (package["type"], package["name"], package["version"]) != (package_type, name, version)
            ]
            return 204, None
        if method == "DELETE" and parts[:2] == ["admin", "users"]:
            del self.users[parts[2]]
            return 204, None
        return 500, {"unexpected": [method, path, body]}


def self_signed(cert, key):
    """Writes a certificate for 127.0.0.1 and its key, made in Python, so the suite needs no openssl on its machine."""
    import datetime
    import ipaddress

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    private = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1")])
    now = datetime.datetime.now(datetime.timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(private.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(private, hashes.SHA256())
    )
    cert.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key.write_bytes(
        private.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        )
    )


@pytest.fixture
def forge(tmp_path):
    state = Forge()
    cert = tmp_path / "ca.pem"
    key = tmp_path / "server-key.pem"
    self_signed(cert, key)
    cert.chmod(0o644)
    state.port = 443
    state.ca = cert
    return state


@pytest.fixture
def https_forge(forge, tmp_path):
    state = forge

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def handle_request(self):
            assert self.headers.get("Authorization") == "token " + ADMIN_TOKEN
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            if urlsplit(self.path).path == "/redirected":
                state.redirected.append(self.headers.get("Authorization"))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"username":"already-taken"}')
                return
            if state.redirect:
                self.send_response(307)
                self.send_header("Location", f"https://127.0.0.1:{self.server.server_port}/redirected")
                self.end_headers()
                return
            status, answer = state.respond(self.command, self.path, json.loads(body) if body else None)
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            if answer is not None:
                self.wfile.write(json.dumps(answer).encode())

        do_GET = do_POST = do_PUT = do_DELETE = handle_request

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.load_cert_chain(forge.ca, tmp_path / "server-key.pem")
    server.socket = tls.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    state.port = server.server_port
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


PERSON_RECORD = "role=project-admin\nprojects=\nlocked=false\nlaptop=laptop ssh-ed25519 AAAA wg= 10.73.7.3\n"


@pytest.fixture
def project_host(tmp_path, forge, push_host):
    etc = tmp_path / "project-etc"
    etc.mkdir(mode=0o700)
    (etc / "people").mkdir(mode=0o700)
    for person in ("alice", "bob"):
        (etc / "people" / f"{person}.conf").write_text(PERSON_RECORD)
        (etc / "people" / f"{person}.conf").chmod(0o600)
    (etc / "forge.conf").write_text(f"address=127.0.0.1\nport={forge.port}\naccount=porelo-forge\n")
    (etc / "forge.conf").chmod(0o600)
    cli_calls = []

    def cli(arguments, **_kwargs):
        cli_calls.append(arguments)
        if arguments[:2] == ["/usr/bin/id", "-u"]:
            return subprocess.CompletedProcess(arguments, 0, "1234\n", "")
        if "create" in arguments:
            name = arguments[arguments.index("--username") + 1]
            forge.users[name] = {}
            return subprocess.CompletedProcess(arguments, 0, "discarded-random-password", "")
        if "generate-access-token" in arguments:
            name = arguments[arguments.index("--username") + 1]
            token = ADMIN_TOKEN if name == "porelo-admin" else PUBLISHER_TOKEN
            return subprocess.CompletedProcess(arguments, 0, token + "\n", "")
        raise AssertionError(arguments)

    return dict(etc=etc, forge=forge, cli=cli, cli_calls=cli_calls, push=push_host, tmp=tmp_path)


@pytest.fixture(params=["memory", "https"])
def api_host(request, project_host):
    """Run API behavior separately from the HTTPS transport so socket restrictions do not hide unit results."""
    if request.param == "https":
        forge = request.getfixturevalue("https_forge")
        settings = project_host["etc"] / "forge.conf"
        settings.write_text(settings.read_text().replace("port=443\n", f"port={forge.port}\n"))
    else:
        project_host["memory"] = True
    return project_host


@pytest.fixture
def memory_host(project_host):
    project_host["memory"] = True
    return project_host


class MemoryOpener:
    """An in-process API stand-in for unit checks; the HTTPS parameter exercises the actual server."""

    def __init__(self, forge):
        self.forge = forge

    def open(self, request, **_kwargs):
        assert request.headers["Authorization"] == "token " + ADMIN_TOKEN
        if self.forge.redirect:
            raise urllib.error.HTTPError(request.full_url, 307, "redirect", {}, None)
        code, value = self.forge.respond(
            request.method, request.full_url, json.loads(request.data) if request.data else None
        )
        if code >= 400:
            raise urllib.error.HTTPError(request.full_url, code, "fixture", {}, None)
        response = io.BytesIO(json.dumps(value).encode() if value is not None else b"")
        response.status = code
        return response


def project(
    host,
    monkeypatch,
    capsys,
    *arguments,
    uid=0,
    overrides=None,
    central_token=CENTRAL_TOKEN,
    token_error=None,
    tty=False,
    piped=None,
):
    # Only this loaded test namespace is changed; the installed root entry point has no environment overrides.
    namespace = runpy.run_path(str(SCRIPT), run_name="project_test")
    values = namespace["main"].__globals__
    values.update(
        ETC=str(host["etc"]),
        CONF=str(host["etc"] / "forge.conf"),
        CA=str(host["forge"].ca),
        ROOT_UID=os.getuid(),
        TRUST_ANCHOR=str(host["tmp"]),
        PUSH=str(host["push"]["command"]),
    )
    values.update(overrides or {})
    real_run = subprocess.run

    def commands(arguments, **kwargs):
        if arguments[0] in ("/usr/bin/id", "/usr/sbin/runuser"):
            return host["cli"](arguments, **kwargs)
        return real_run(arguments, **kwargs)

    def read_token(*_args):
        if token_error is not None:
            raise token_error
        return central_token

    with monkeypatch.context() as patch:
        patch.setattr(os, "geteuid", lambda: uid)
        patch.setattr(sys, "argv", [str(SCRIPT), *arguments])
        patch.setattr(subprocess, "run", commands)
        typed = type("Typed", (io.StringIO,), {"isatty": lambda self: True})
        given = piped if piped is not None else "" if token_error else central_token + "\n"
        patch.setattr(sys, "stdin", (typed if tty else io.StringIO)(given))
        patch.setattr(__import__("getpass"), "getpass", read_token)
        patch.setattr(os, "environ", os.environ.copy())
        if host.get("memory"):
            patch.setattr(urllib.request, "build_opener", lambda *_args: MemoryOpener(host["forge"]))
        previous_mask = os.umask(0o077)
        os.umask(previous_mask)
        try:
            values["main"]()
            code = 0
        except SystemExit as error:
            code = error.code
        finally:
            os.umask(previous_mask)
    output = capsys.readouterr()
    if code:
        assert not output.out and output.err.startswith("porelo-host-project: "), (code, output)
    records = "".join(path.read_text() for path in (host["etc"] / "projects").glob("*.conf"))
    for token in (ADMIN_TOKEN, PUBLISHER_TOKEN, CENTRAL_TOKEN, "discarded-random-password"):
        assert token not in output.out + output.err + records, "a credential escaped into output or a record"
        assert all(token not in str(call) for call in host["cli_calls"]), "a credential reached a command argument"
    assert_no_token_anywhere(host["push"], output.out + output.err + records)
    return code, output.out, output.err


def assert_refused(host, result, diagnostic, expected_code):
    code, out, err = result
    assert code == expected_code, (code, out, err)
    assert err.startswith("porelo-host-project: ") and diagnostic in err, err
    assert not out, "a refused call must not print a success record"
    assert not [call for call in host["forge"].calls if call[0] != "GET"], "a refusal mutated the forge"
    assert not host["cli_calls"], "a refusal generated a token or account before local checks finished"


@pytest.mark.parametrize(
    "arguments, diagnostic",
    [
        (("add", "../escape", "alice", "--signed-by", KEY), "project"),
        (("add", "A", "alice", "--signed-by", KEY), "project"),
        (("add", "a" * 41, "alice", "--signed-by", KEY), "project"),
        (("add", "alpha-", "alice", "--signed-by", KEY), "project"),
        (("add", "alpha", "../alice", "--signed-by", KEY), "admin"),
        (("add", "alpha", "alice", "--signed-by", "0123456789ABCDEF0123456789ABCDEF01234567"), "signing key"),
        (("add", "alpha", "alice"), "usage"),
        (("remove", "alpha", "extra"), "usage"),
        (("other",), "usage"),
    ],
)
def test_invalid_calls_change_nothing(project_host, monkeypatch, capsys, arguments, diagnostic):
    """Prevent path traversal and malformed calls from creating accounts or records."""
    assert_refused(project_host, project(project_host, monkeypatch, capsys, *arguments), diagnostic, 64)
    assert not (project_host["etc"] / "projects").exists()


def test_nonroot_is_refused_before_reading_arguments_or_files(project_host, monkeypatch, capsys):
    """Prevent an unauthorized caller from reaching root's files or the forge."""
    result = project(project_host, monkeypatch, capsys, "nonsense", uid=1000)
    assert_refused(project_host, result, "root", 69)
    assert not project_host["forge"].calls


@pytest.mark.parametrize("defect", ["missing", "symlink", "writable", "readable", "directory", "owner"])
def test_an_untrusted_person_record_changes_nothing(project_host, monkeypatch, capsys, defect):
    """Prevent a forged person record from granting ownership of a project."""
    record = project_host["etc"] / "people/alice.conf"
    if defect in ("missing", "symlink", "directory"):
        record.unlink()
    if defect == "symlink":
        record.symlink_to(project_host["etc"] / "people/bob.conf")
    elif defect == "directory":
        record.mkdir()
    elif defect in ("writable", "readable"):
        record.chmod(0o666 if defect == "writable" else 0o644)
    if defect == "owner":
        lstat = os.lstat

        def wrong_owner(path, *args, **kwargs):
            actual = lstat(path, *args, **kwargs)
            if str(path) == str(record):
                fields = list(actual)
                fields[4] += 1
                return os.stat_result(fields)
            return actual

        monkeypatch.setattr(os, "lstat", wrong_owner)
    result = project(project_host, monkeypatch, capsys, "add", "alpha", "alice", "--signed-by", KEY)
    if defect == "missing":
        assert_refused(project_host, result, "alice is no person on this host", 65)
    else:
        assert_refused(project_host, result, "root", 69)
    assert not (project_host["etc"] / "projects").exists()


@pytest.mark.parametrize(
    "record",
    [PERSON_RECORD.replace("locked=false", "locked=true"), PERSON_RECORD.replace("role=project-admin", "role=x")],
)
def test_a_locked_or_other_person_cannot_own_a_project(project_host, monkeypatch, capsys, record):
    """Prevent registering a project for an admin the host has locked out, or who is no project admin."""
    (project_host["etc"] / "people/alice.conf").write_text(record)
    result = project(project_host, monkeypatch, capsys, "add", "alpha", "alice", "--signed-by", KEY)
    assert_refused(project_host, result, "alice", 65)
    assert not project_host["forge"].calls


def test_an_admin_purged_while_waiting_for_the_lock_owns_no_project(project_host, monkeypatch, capsys):
    """Prevent a purge holding the lock from being followed by a project for the person it removed."""
    flock = fcntl.flock

    def purge_first(descriptor, operation):
        (project_host["etc"] / "people/alice.conf").unlink(missing_ok=True)
        return flock(descriptor, operation)

    monkeypatch.setattr(fcntl, "flock", purge_first)
    result = project(project_host, monkeypatch, capsys, "add", "alpha", "alice", "--signed-by", KEY)
    assert result[0] == 65 and "alice is no person on this host" in result[2], result
    assert not project_host["forge"].calls


def test_an_existing_record_is_never_overwritten(project_host, monkeypatch, capsys):
    """Prevent re-registration from replacing the pinned signing key or original owner."""
    directory = project_host["etc"] / "projects"
    directory.mkdir(mode=0o700)
    record = directory / "alpha.conf"
    record.write_text("original\n")
    assert_refused(
        project_host,
        project(project_host, monkeypatch, capsys, "add", "alpha", "alice", "--signed-by", KEY),
        "exists",
        65,
    )
    assert record.read_text() == "original\n"


@pytest.mark.parametrize("kind", ["organization", "user", "publisher", "admin"])
def test_forge_name_collisions_change_nothing(api_host, monkeypatch, capsys, kind):
    """Prevent taking over an existing forge identity or creating a project without its admin."""
    project_host = api_host
    forge = project_host["forge"]
    if kind == "organization":
        forge.organizations["alpha"] = {"username": "alpha"}
    elif kind == "user":
        forge.users["alpha"] = {}
    elif kind == "publisher":
        forge.users["porelo-publisher-alpha"] = {}
    else:
        del forge.users["alice"]
    result = project(project_host, monkeypatch, capsys, "add", "alpha", "alice", "--signed-by", KEY)
    assert result[0] == 65 and kind in result[2], result
    assert not [call for call in forge.calls if call[0] != "GET"]
    assert not any("create" in call for call in project_host["cli_calls"])
    assert not (project_host["etc"] / "projects").exists()


def test_add_creates_only_the_project_owner_and_package_publisher(api_host, monkeypatch, capsys):
    """Prevent cross-project publishing, leaked credentials, and a record that disagrees with the forge."""
    project_host = api_host
    forge = project_host["forge"]
    for name, admin in (("alpha", "alice"), ("beta", "bob")):
        code, out, err = project(project_host, monkeypatch, capsys, "add", name, admin, "--signed-by", KEY)
        assert code == 0, err
        publisher = "porelo-publisher-" + name
        assert json.loads(out) == dict(project=name, admin=admin, organization=name, publisher=publisher)
        assert out == f'{{"project":"{name}","admin":"{admin}","organization":"{name}","publisher":"{publisher}"}}\n'
        record = project_host["etc"] / "projects" / f"{name}.conf"
        assert record.read_text() == f"admin={admin}\nsigned_by={KEY}\npublisher={publisher}\n"
        assert record.stat().st_mode & 0o777 == 0o600
        assert record.stat().st_uid == os.getuid()
        teams = [team for team in forge.teams.values() if team["org"] == name]
        assert len(teams) == 2
        owner = next(team for team in teams if team["name"] == "Owners")
        assert owner["members"] == [admin]
        team = next(team for team in teams if team["name"] == "publishers")
        assert team == dict(
            org=name,
            name="publishers",
            members=[publisher],
            permission="write",
            units=["repo.packages"],
            units_map={"repo.packages": "write"},
            includes_all_repositories=False,
            can_create_org_repo=False,
        )
        assert forge.secrets[(name, "PORELO_PUBLISHER_TOKEN")] == PUBLISHER_TOKEN
    assert set(forge.organizations) == {"alpha", "beta"}
    assert set(forge.users) == {"alice", "bob", "porelo-publisher-alpha", "porelo-publisher-beta"}
    for directory in ("projects", "people"):
        assert (project_host["etc"] / directory).stat().st_mode & 0o777 == 0o700
    scopes = [call[call.index("--scopes") + 1] for call in project_host["cli_calls"] if "--scopes" in call]
    assert scopes.count("write:package") == 2


def test_unknown_removal_never_reaches_the_forge(project_host, monkeypatch, capsys):
    """Prevent deleting an organization that has not been registered on this host."""
    assert_refused(project_host, project(project_host, monkeypatch, capsys, "remove", "unknown"), "unknown", 65)


@pytest.mark.parametrize("reference", ["refs/heads/task", "refs/tags/task"], ids=["branch", "tag"])
def test_remove_refuses_unpushed_commits_then_removes_only_the_project(api_host, monkeypatch, capsys, reference):
    """Prevent losing any branch's work or deleting another project's publisher and packages."""
    host = api_host
    forge = host["forge"]
    assert project(host, monkeypatch, capsys, "add", "alpha", "alice", "--signed-by", KEY)[0] == 0
    assert project(host, monkeypatch, capsys, "add", "beta", "bob", "--signed-by", KEY)[0] == 0
    local = host["tmp"] / "local" / "alpha" / "stand-in.git"
    central = host["tmp"] / "central" / "stand-in.git"
    bare(local, source=central)
    pending = commit(local, host["tmp"] / "project-work", "pending")
    git("--git-dir", str(local), "update-ref", reference, pending)
    git("--git-dir", str(local), "update-ref", "refs/heads/main", pending + "~1")
    forge.repositories["alpha"] = [{"name": "stand-in"}]
    forge.packages["alpha"] = [{"type": "maven", "name": "org.example:demo", "version": "1.0+test"}]
    forge.packages["beta"] = [{"type": "maven", "name": "org.example:other", "version": "1.0"}]
    forge.calls.clear()
    code, out, err = project(host, monkeypatch, capsys, "remove", "alpha")
    assert code == 65 and "stand-in" in err and "unpushed" in err, (code, out, err)
    assert not [call for call in forge.calls if call[0] != "GET"]
    assert (host["etc"] / "projects/alpha.conf").exists()
    assert git("--git-dir", str(central), "rev-parse", "main") != pending
    assert not git("--git-dir", str(central), "for-each-ref", reference)
    git("--git-dir", str(local), "push", str(central), f"{reference}:{reference}")
    code, out, err = project(host, monkeypatch, capsys, "remove", "alpha")
    assert code == 0, err
    assert json.loads(out) == {"project": "alpha", "removed": True, "locked": []}
    assert out == '{"project":"alpha","removed":true,"locked":[]}\n'
    assert not (host["etc"] / "projects/alpha.conf").exists()
    assert set(forge.organizations) == {"beta"}
    assert set(forge.users) == {"alice", "bob", "porelo-publisher-beta"}
    assert set(forge.secrets) == {("beta", "PORELO_PUBLISHER_TOKEN")}
    assert not forge.packages["alpha"]
    assert forge.packages["beta"] == [{"type": "maven", "name": "org.example:other", "version": "1.0"}]
    assert list(host["push"]["temporary"].iterdir()) == []


@pytest.mark.parametrize("failure", ["server", "redirect", "ca"])
def test_an_untrusted_or_unavailable_forge_changes_nothing(api_host, monkeypatch, capsys, failure):
    """Prevent an API failure, untrusted certificate, or redirect from granting access or leaking a token."""
    project_host = api_host
    forge = project_host["forge"]
    overrides = None
    if failure == "server":
        forge.failure = ("GET", "/api/v1/orgs/alpha")
    elif failure == "redirect":
        forge.redirect = True
    else:
        ca = project_host["tmp"] / "bad-ca.pem"
        ca.write_text("not a certificate")
        overrides = {"CA": str(ca)}
    result = project(
        project_host, monkeypatch, capsys, "add", "alpha", "alice", "--signed-by", KEY, overrides=overrides
    )
    assert result[0] == (65 if failure == "redirect" else 69) and result[2].startswith("porelo-host-project: "), result
    assert not [call for call in forge.calls if call[0] != "GET"]
    assert not (project_host["etc"] / "projects").exists()
    assert not forge.redirected, "the admin token followed a forge redirect"


@pytest.mark.parametrize("directory, defect", [("people", "symlink"), ("people", "writable"), ("projects", "readable")])
def test_untrusted_record_directories_are_refused_before_the_forge(
    project_host, monkeypatch, capsys, directory, defect
):
    """Prevent a shared or redirected records directory from granting ownership or replacing a signing key."""
    path = project_host["etc"] / directory
    if directory == "projects":
        path.mkdir(mode=0o700)
    if defect == "symlink":
        path.rename(project_host["etc"] / "other-people")
        path.symlink_to(project_host["etc"] / "other-people")
    else:
        path.chmod(0o777 if defect == "writable" else 0o755)
    result = project(project_host, monkeypatch, capsys, "add", "alpha", "alice", "--signed-by", KEY)
    assert_refused(project_host, result, "root", 69)
    assert not project_host["forge"].calls


@pytest.mark.parametrize(
    "field, value", [("admin", "../alice"), ("signed_by", "bad"), ("publisher", "porelo-publisher-beta")]
)
def test_a_corrupt_project_record_prevents_deleting_any_identity(memory_host, monkeypatch, capsys, field, value):
    """Prevent a tampered project record from deleting another project's publisher."""
    host = memory_host
    assert project(host, monkeypatch, capsys, "add", "alpha", "alice", "--signed-by", KEY)[0] == 0
    record = host["etc"] / "projects/alpha.conf"
    values = dict(admin="alice", signed_by=KEY, publisher="porelo-publisher-alpha")
    values[field] = value
    record.write_text("".join(f"{key}={entry}\n" for key, entry in values.items()))
    host["forge"].calls.clear()
    host["cli_calls"].clear()
    result = project(host, monkeypatch, capsys, "remove", "alpha")
    assert_refused(host, result, field, 65)
    assert not host["forge"].calls
    assert record.exists()


@pytest.mark.parametrize("body", [None, [], "not an organization"])
def test_an_ambiguous_name_lookup_is_never_treated_as_a_free_name(memory_host, monkeypatch, capsys, body):
    """Prevent a malformed successful lookup from bypassing the name collision check."""
    host = memory_host
    host["forge"].responses[("GET", "/api/v1/orgs/alpha")] = (200, body)
    result = project(host, monkeypatch, capsys, "add", "alpha", "alice", "--signed-by", KEY)
    assert result[0] == 65, result
    assert not [call for call in host["forge"].calls if call[0] != "GET"]
    assert not (host["etc"] / "projects").exists()


@pytest.mark.parametrize("defect", ["repeat", "shape", "name", "package", "missing-source"])
def test_incomplete_repository_or_package_checks_prevent_all_deletion(memory_host, monkeypatch, capsys, defect):
    """Prevent a truncated or unverifiable reference set from allowing deletion of unpushed work."""
    host = memory_host
    forge = host["forge"]
    assert project(host, monkeypatch, capsys, "add", "alpha", "alice", "--signed-by", KEY)[0] == 0
    if defect == "repeat":
        forge.pages["/api/v1/orgs/alpha/repos"] = [[{"name": "stand-in"}]]
    elif defect == "shape":
        forge.responses[("GET", "/api/v1/orgs/alpha/repos")] = (200, {"name": "stand-in"})
    elif defect == "name":
        forge.repositories["alpha"] = [{"name": "../other"}]
    elif defect == "package":
        forge.packages["alpha"] = [{"type": "maven", "name": "demo"}]
    else:
        forge.repositories["alpha"] = [{"name": "unknown-source"}]
    forge.calls.clear()
    code, out, err = project(host, monkeypatch, capsys, "remove", "alpha")
    assert code == (69 if defect == "missing-source" else 65) and err.startswith("porelo-host-project: "), (
        code,
        out,
        err,
    )
    assert not [call for call in forge.calls if call[0] != "GET"]
    assert (host["etc"] / "projects/alpha.conf").exists()
    assert list(host["push"]["temporary"].iterdir()) == []


def test_a_later_repository_page_cannot_hide_unpushed_work(memory_host, monkeypatch, capsys):
    """Prevent deleting a repository omitted by a first-page-only safety check."""
    host = memory_host
    forge = host["forge"]
    assert project(host, monkeypatch, capsys, "add", "alpha", "alice", "--signed-by", KEY)[0] == 0
    forge.pages["/api/v1/orgs/alpha/repos"] = [[{"name": "stand-in"}], [{"name": "unknown-source"}], []]
    forge.calls.clear()
    code, out, err = project(host, monkeypatch, capsys, "remove", "alpha")
    assert code == 69 and "unknown-source" in err, (code, out, err)
    assert any("page=2" in query for method, path, query in forge.queries if path.endswith("/repos"))
    assert not [call for call in forge.calls if call[0] != "GET"]


@pytest.mark.parametrize("path", ["/orgs/alpha/teams", "/orgs/alpha/actions/secrets/PORELO_PUBLISHER_TOKEN"])
def test_failed_registration_removes_its_own_partial_identities(memory_host, monkeypatch, capsys, path):
    """Prevent an API failure from leaving an unrecorded organization or reusable publisher behind."""
    host = memory_host
    forge = host["forge"]
    forge.failure = ("PUT" if "/secrets/" in path else "POST", "/api/v1" + path)
    code, out, err = project(host, monkeypatch, capsys, "add", "alpha", "alice", "--signed-by", KEY)
    # A forge answering 503 is a forge not working: something needed is missing.
    assert code == 69 and "HTTP 503" in err and not out, (code, out, err)
    assert not forge.organizations
    assert set(forge.users) == {"alice", "bob"}
    assert list((host["etc"] / "projects").iterdir()) == []


def test_a_record_created_during_registration_cannot_be_overwritten(memory_host, monkeypatch, capsys):
    """Prevent two writers from replacing the first registered admin and signing key."""
    host = memory_host
    record = host["etc"] / "projects/alpha.conf"
    original = f"admin=bob\nsigned_by={KEY}\npublisher=porelo-publisher-alpha\n"

    def concurrent_writer(operation):
        def publish(source, target, *args, **kwargs):
            record.write_text(original)
            record.chmod(0o600)
            return operation(source, target, *args, **kwargs)

        return publish

    monkeypatch.setattr(os, "link", concurrent_writer(os.link))
    monkeypatch.setattr(os, "rename", concurrent_writer(os.rename))
    code, out, err = project(host, monkeypatch, capsys, "add", "alpha", "alice", "--signed-by", KEY)
    assert code == 65 and not out, (code, out, err)
    assert record.read_text() == original
    assert not host["forge"].organizations
    assert set(host["forge"].users) == {"alice", "bob"}


@pytest.mark.parametrize("failure", ["uid", "admin-token", "publisher-create", "publisher-token"])
def test_failed_cli_commands_never_publish_a_record_or_credentials(memory_host, monkeypatch, capsys, failure):
    """Prevent a failed or malformed CLI response from exposing credentials or leaving unrecorded access."""
    host = memory_host
    original = host["cli"]

    def cli(arguments, **kwargs):
        failing = (
            (failure == "uid" and arguments[0] == "/usr/bin/id")
            or (failure == "publisher-create" and "create" in arguments)
            or (failure == "admin-token" and "porelo-admin" in arguments)
            or (failure == "publisher-token" and "write:package" in arguments)
        )
        if failing:
            host["cli_calls"].append(arguments)
            return subprocess.CompletedProcess(arguments, 1, ADMIN_TOKEN, PUBLISHER_TOKEN)
        return original(arguments, **kwargs)

    host["cli"] = cli
    code, out, err = project(host, monkeypatch, capsys, "add", "alpha", "alice", "--signed-by", KEY)
    assert code == 69 and not out and err.startswith("porelo-host-project: "), (
        code,
        out,
        err,
    )
    assert not (host["etc"] / "projects/alpha.conf").exists()
    assert not host["forge"].organizations
    assert set(host["forge"].users) == {"alice", "bob"}


def test_failed_cleanup_still_attempts_both_identities_and_names_leftovers(memory_host, monkeypatch, capsys):
    """Prevent one failed cleanup from silently leaving another usable publisher account behind."""
    host = memory_host
    forge = host["forge"]
    forge.failure = ("PUT", "/api/v1/orgs/alpha/actions/secrets/PORELO_PUBLISHER_TOKEN")
    forge.responses[("DELETE", "/api/v1/orgs/alpha")] = (503, {"message": ADMIN_TOKEN})
    code, out, err = project(host, monkeypatch, capsys, "add", "alpha", "alice", "--signed-by", KEY)
    assert code == 69 and not out, (code, out, err)
    assert "cleanup left organization alpha" in err, err
    assert set(forge.users) == {"alice", "bob"}
    assert not (host["etc"] / "projects/alpha.conf").exists()


def test_the_callers_umask_cannot_leave_unusable_record_directories(memory_host, monkeypatch, capsys):
    """Prevent a restrictive inherited umask from leaving a half-created registration directory."""
    host = memory_host
    previous = os.umask(0o777)
    try:
        code, out, err = project(host, monkeypatch, capsys, "add", "alpha", "alice", "--signed-by", KEY)
        assert code == 0, (out, err)
        assert (host["etc"] / "projects").stat().st_mode & 0o777 == 0o700
    finally:
        os.umask(previous)
        directory = host["etc"] / "projects"
        if directory.exists():
            directory.chmod(0o700)


@pytest.mark.parametrize(
    "wire", [KEY_WIRE, KEY_WIRE[:19] + bytes(32), KEY_WIRE[:19] + b"\xff" * 32], ids=["range", "zero", "ones"]
)
def test_canonical_ed25519_signers_are_stored_exactly(memory_host, monkeypatch, capsys, wire):
    """Prevent pinning a different signing key from the exact canonical key supplied by the project."""
    host = memory_host
    key = "ssh-ed25519 " + base64.b64encode(wire).decode("ascii")
    code, out, err = project(host, monkeypatch, capsys, "add", "alpha", "alice", "--signed-by", key)
    assert code == 0, (code, out, err)
    assert (
        host["etc"] / "projects/alpha.conf"
    ).read_text() == f"admin=alice\nsigned_by={key}\npublisher=porelo-publisher-alpha\n"


@pytest.mark.parametrize(
    "key",
    [
        "",
        "0123456789ABCDEF0123456789ABCDEF01234567",
        "ssh-rsa " + KEY.split(" ")[1],
        "ssh-ed25519 " + base64.b64encode(KEY_WIRE.replace(b"ssh-ed25519", b"ssh-ed25518")).decode(),
        "ssh-ed25519 " + base64.b64encode(KEY_WIRE[:15] + b"\x00\x00\x00\x1f" + KEY_WIRE[19:]).decode(),
        "ssh-ed25519 " + base64.b64encode(KEY_WIRE[:-1]).decode(),
        "ssh-ed25519 " + base64.b64encode(KEY_WIRE + b"\x00").decode(),
        "ssh-ed25519 " + "!" * 68,
        "ssh-ed25519 \u00e9",
        KEY + "=",
        KEY + " comment",
        KEY + "\n",
        KEY + " ",
        " " + KEY,
        KEY.replace(" ", "\t"),
        KEY.replace(" ", "  "),
    ],
    ids=[
        "empty",
        "fingerprint",
        "rsa",
        "wire-type",
        "wire-length",
        "short",
        "long",
        "bad-base64",
        "unicode",
        "padding",
        "comment",
        "newline",
        "trailing-space",
        "leading-space",
        "tab",
        "two-spaces",
    ],
)
def test_invalid_signing_keys_never_reach_the_forge(memory_host, monkeypatch, capsys, key):
    """Prevent a malformed or ambiguous signer from becoming the project's pinned authority."""
    host = memory_host
    result = project(host, monkeypatch, capsys, "add", "alpha", "alice", "--signed-by", key)
    assert_refused(host, result, "signing key", 64)
    assert not host["forge"].calls
    assert not (host["etc"] / "projects").exists()


@pytest.mark.parametrize(
    "code, expected",
    [(65, 65), (69, 69), (73, 73), (64, 69), (66, 69), (77, 69), (75, 64), (130, 64), (143, 64), (1, 69)],
)
def test_comparison_failures_keep_the_contract_exit_code(memory_host, monkeypatch, capsys, code, expected):
    """Prevent a missing comparison dependency or write failure from being reported as unpushed work."""
    host = memory_host
    assert project(host, monkeypatch, capsys, "add", "alpha", "alice", "--signed-by", KEY)[0] == 0
    host["forge"].repositories["alpha"] = [{"name": "stand-in"}]
    host["forge"].calls.clear()
    host["push"]["command"].write_text(f"#!/bin/sh\nexit {code}\n")
    result = project(host, monkeypatch, capsys, "remove", "alpha")
    assert result[0] == expected, result
    assert not [call for call in host["forge"].calls if call[0] != "GET"]
    assert (host["etc"] / "projects/alpha.conf").exists()


@pytest.mark.parametrize("failure", ["empty", "newline", "eof", "interrupt"])
def test_missing_or_canceled_token_input_is_an_input_refusal(memory_host, monkeypatch, capsys, failure):
    """Prevent a canceled credential prompt from deleting data or claiming a dependency failed."""
    host = memory_host
    assert project(host, monkeypatch, capsys, "add", "alpha", "alice", "--signed-by", KEY)[0] == 0
    host["forge"].repositories["alpha"] = [{"name": "stand-in"}]
    host["forge"].calls.clear()
    value = "" if failure == "empty" else "invalid\ninput" if failure == "newline" else CENTRAL_TOKEN
    error = EOFError() if failure == "eof" else KeyboardInterrupt() if failure == "interrupt" else None
    typed = failure in ("eof", "interrupt")
    result = project(host, monkeypatch, capsys, "remove", "alpha", central_token=value, token_error=error, tty=typed)
    assert result[0] == 64, result
    assert not [call for call in host["forge"].calls if call[0] != "GET"]
    assert (host["etc"] / "projects/alpha.conf").exists()


@pytest.mark.parametrize(
    "operation",
    ["directory", "temporary", "mode", "write", "sync", "publish", "temporary-cleanup", "record-removal", "stdout"],
)
def test_write_failures_are_distinct_from_dependency_refusals(memory_host, monkeypatch, capsys, operation):
    """Prevent failed record writes or deletion from being mistaken for a successful registration or missing dependency."""
    import builtins
    import tempfile

    host = memory_host
    record = host["etc"] / "projects/alpha.conf"
    if operation == "record-removal":
        assert project(host, monkeypatch, capsys, "add", "alpha", "alice", "--signed-by", KEY)[0] == 0

    def no_space(*_args, **_kwargs):
        raise OSError(errno.ENOSPC, "fixture write failed")

    if operation == "directory":
        monkeypatch.setattr(os, "makedirs", no_space)
    elif operation == "temporary":
        monkeypatch.setattr(tempfile, "mkstemp", no_space)
    elif operation == "mode":
        monkeypatch.setattr(os, "fchmod", no_space)
    elif operation == "write":
        monkeypatch.setattr(os, "fdopen", no_space)
    elif operation == "sync":
        monkeypatch.setattr(os, "fsync", no_space)
    elif operation == "publish":
        monkeypatch.setattr(os, "link", no_space)
    elif operation in ("temporary-cleanup", "record-removal"):
        unlink = os.unlink

        def cannot_unlink(path, *args, **kwargs):
            if str(path) == str(record) or Path(path).name.startswith(".alpha-"):
                no_space()
            return unlink(path, *args, **kwargs)

        monkeypatch.setattr(os, "unlink", cannot_unlink)
    else:
        emit = builtins.print

        def cannot_print(*args, **kwargs):
            if kwargs.get("file", sys.stdout) is sys.stdout:
                no_space()
            return emit(*args, **kwargs)

        monkeypatch.setattr(builtins, "print", cannot_print)
    arguments = ("remove", "alpha") if operation == "record-removal" else ("add", "alpha", "alice", "--signed-by", KEY)
    result = project(host, monkeypatch, capsys, *arguments)
    assert result[0] == 73 and "cannot write" in result[2], result


@pytest.mark.parametrize(
    "error", [http.client.BadStatusLine("invalid HTTP"), http.client.IncompleteRead(ADMIN_TOKEN.encode(), 100)]
)
def test_an_unreadable_http_reply_is_a_dependency_refusal(memory_host, monkeypatch, capsys, error):
    """Prevent malformed HTTP replies from bypassing the refusal codes or exposing a partial credential-bearing body."""
    host = memory_host

    def incomplete(*_args):
        raise error

    host["forge"].respond = incomplete
    result = project(host, monkeypatch, capsys, "add", "alpha", "alice", "--signed-by", KEY)
    assert result[0] == 69 and type(error).__name__ in result[2], result
    assert not [call for call in host["forge"].calls if call[0] != "GET"]
    assert not (host["etc"] / "projects").exists()


@pytest.mark.parametrize("piped, code", [(CENTRAL_TOKEN + "\n", 0), (CENTRAL_TOKEN + "\nmore\n", 64), ("", 64)])
def test_a_piped_token_is_its_one_line_and_never_prompted(memory_host, monkeypatch, capsys, piped, code):
    """Prevent the interface's piped token from hanging on a prompt, or more than its one line being taken as it."""
    host = memory_host
    assert project(host, monkeypatch, capsys, "add", "alpha", "alice", "--signed-by", KEY)[0] == 0
    host["forge"].repositories["alpha"] = [{"name": "stand-in"}]
    # The comparison is stood in for: it passes only when it was handed exactly the piped token.
    host["push"]["command"].write_text(f'#!/bin/sh\nread -r given; [ "$given" = "{CENTRAL_TOKEN}" ] || exit 9\n')
    error = AssertionError("a pipe must not be prompted")
    result = project(host, monkeypatch, capsys, "remove", "alpha", token_error=error, piped=piped)
    assert result[0] == code, result
    assert (host["etc"] / "projects/alpha.conf").exists() == bool(code), "only a refusal keeps the project"


def test_add_accepts_any_unlocked_member_and_records_project_admin_in_fixed_order(memory_host, monkeypatch, capsys):
    """Prevent rejecting an unlocked project member without legacy role= lines, or omitting their admin membership."""
    host = memory_host
    laptop_line = "laptop=laptop ssh-ed25519 AAAA wg= 10.73.7.3\n"
    (host["etc"] / "people/bob.conf").write_text("member=zeta developer\nlocked=false\n" + laptop_line)
    carol = host["etc"] / "people/carol.conf"
    carol.write_text("locked=false\n" + laptop_line)
    carol.chmod(0o600)
    host["forge"].users["carol"] = {}

    assert project(host, monkeypatch, capsys, "add", "alpha", "alice", "--signed-by", KEY)[0] == 0
    assert (host["etc"] / "people/alice.conf").read_text() == (
        "member=hand\nmember=alpha project-admin\nlocked=false\n" + laptop_line
    )
    assert project(host, monkeypatch, capsys, "add", "beta", "bob", "--signed-by", KEY)[0] == 0
    assert (host["etc"] / "people/bob.conf").read_text() == (
        "member=beta project-admin\nmember=zeta developer\nlocked=false\n" + laptop_line
    )
    host["forge"].calls.clear()
    host["cli_calls"].clear()
    refused = project(host, monkeypatch, capsys, "add", "gamma", "carol", "--signed-by", KEY)
    assert_refused(host, refused, "carol", 65)
    assert not (host["etc"] / "projects/gamma.conf").exists()


def test_remove_drops_the_project_and_locks_only_people_left_with_no_membership_after_releasing_the_lock(
    memory_host, monkeypatch, capsys
):
    """Prevent leaving a zero-membership person unlocked, locking remaining members, or deadlocking on forge.conf."""
    host = memory_host
    laptop_line = "laptop=laptop ssh-ed25519 AAAA wg= 10.73.7.3\n"
    people = host["etc"] / "people"
    assert project(host, monkeypatch, capsys, "add", "alpha", "alice", "--signed-by", KEY)[0] == 0
    assert project(host, monkeypatch, capsys, "add", "beta", "bob", "--signed-by", KEY)[0] == 0
    records = {
        "alice": "member=hand\nmember=alpha project-admin\nlocked=false\n" + laptop_line,
        "bob": "member=alpha developer\nmember=beta project-admin\nlocked=false\n" + laptop_line,
        "carol": "member=alpha developer\nlocked=false\n" + laptop_line,
        "dan": "member=alpha project-admin\nmember=alpha developer\nlocked=false\n" + laptop_line,
        "eve": "locked=true\n" + laptop_line,
    }
    for name, content in records.items():
        path = people / f"{name}.conf"
        path.write_text(content)
        path.chmod(0o600)

    person_helper = host["tmp"] / "porelo-host-person"
    calls_file = host["tmp"] / "person-lock-calls.txt"
    person_helper.write_text(
        "#!/usr/bin/python3 -I\n"
        "import fcntl, json, pathlib, sys\n"
        f"conf = pathlib.Path({str(host['etc'] / 'forge.conf')!r})\n"
        f"people = pathlib.Path({str(people)!r})\n"
        f"log = pathlib.Path({str(calls_file)!r})\n"
        "assert sys.argv[1:] and sys.argv[1] == 'lock' and len(sys.argv) == 3\n"
        "user = sys.argv[2]\n"
        "with conf.open('rb') as mutex:\n"
        "    fcntl.flock(mutex, fcntl.LOCK_EX | fcntl.LOCK_NB)\n"
        "    record = people / f'{user}.conf'\n"
        "    text = record.read_text(encoding='utf-8')\n"
        "    assert 'member=' not in text and 'locked=false\\n' in text\n"
        "    record.write_text(text.replace('locked=false\\n', 'locked=true\\n', 1), encoding='utf-8')\n"
        "with log.open('a', encoding='utf-8') as out:\n"
        "    out.write(user + '\\n')\n"
        "print(json.dumps({'person': user, 'locked': True}, separators=(',', ':')))\n"
    )
    person_helper.chmod(0o700)

    code, out, err = project(host, monkeypatch, capsys, "remove", "alpha", overrides={"PERSON": str(person_helper)})
    assert code == 0, err
    assert json.loads(out) == {"project": "alpha", "removed": True, "locked": ["carol", "dan"]}
    assert out == '{"project":"alpha","removed":true,"locked":["carol","dan"]}\n'
    assert calls_file.read_text().splitlines() == ["carol", "dan"]
    assert (people / "alice.conf").read_text() == "member=hand\nlocked=false\n" + laptop_line
    assert (people / "bob.conf").read_text() == "member=beta project-admin\nlocked=false\n" + laptop_line
    assert (people / "carol.conf").read_text() == "locked=true\n" + laptop_line
    assert (people / "dan.conf").read_text() == "locked=true\n" + laptop_line
    assert (people / "eve.conf").read_text() == "locked=true\n" + laptop_line


@pytest.mark.parametrize("defect, expected", [("corrupt-person", 65), ("missing-person-helper", 69)])
def test_remove_refuses_corrupt_people_or_missing_person_helper_before_deleting_the_project(
    memory_host, monkeypatch, capsys, defect, expected
):
    """Prevent deleting a project on the forge when a person's record is corrupt or the lock helper is missing."""
    host = memory_host
    assert project(host, monkeypatch, capsys, "add", "alpha", "alice", "--signed-by", KEY)[0] == 0
    carol = host["etc"] / "people/carol.conf"
    if defect == "corrupt-person":
        carol.write_text("member=alpha unknown\nlocked=false\nlaptop=laptop ssh-ed25519 AAAA wg= 10.73.7.5\n")
    else:
        carol.write_text("member=alpha developer\nlocked=false\nlaptop=laptop ssh-ed25519 AAAA wg= 10.73.7.5\n")
    carol.chmod(0o600)
    host["forge"].calls.clear()
    host["cli_calls"].clear()
    missing = host["tmp"] / "missing-porelo-host-person"
    result = project(host, monkeypatch, capsys, "remove", "alpha", overrides={"PERSON": str(missing)})
    assert result[0] == expected and not result[1], result
    assert not [call for call in host["forge"].calls if call[0] == "DELETE"]
    assert (host["etc"] / "projects/alpha.conf").exists()


def test_remove_attempts_every_lock_and_fails_when_locking_a_person_fails(memory_host, monkeypatch, capsys):
    """Prevent one failed person lock from leaving another zero-membership person unlocked or claiming success."""
    host = memory_host
    assert project(host, monkeypatch, capsys, "add", "alpha", "alice", "--signed-by", KEY)[0] == 0
    laptop_line = "laptop=laptop ssh-ed25519 AAAA wg= 10.73.7.5\n"
    for name in ("carol", "dan"):
        path = host["etc"] / "people" / f"{name}.conf"
        path.write_text("member=alpha developer\nlocked=false\n" + laptop_line)
        path.chmod(0o600)
    calls_file = host["tmp"] / "person-lock-attempts.txt"
    person_helper = host["tmp"] / "porelo-host-person"
    person_helper.write_text(
        "#!/usr/bin/python3 -I\n"
        "import json, pathlib, sys\n"
        "user = sys.argv[2]\n"
        f"with pathlib.Path({str(calls_file)!r}).open('a', encoding='utf-8') as out:\n"
        "    out.write(user + '\\n')\n"
        "if user == 'carol':\n"
        "    sys.exit(69)\n"
        f"record = pathlib.Path({str(host['etc'] / 'people')!r}) / f'{{user}}.conf'\n"
        "record.write_text(record.read_text(encoding='utf-8').replace('locked=false', 'locked=true', 1))\n"
        "print(json.dumps({'person': user, 'locked': True}, separators=(',', ':')))\n"
    )
    person_helper.chmod(0o700)

    code, out, err = project(host, monkeypatch, capsys, "remove", "alpha", overrides={"PERSON": str(person_helper)})
    assert code == 69 and not out and "carol" in err, (code, out, err)
    assert calls_file.read_text().splitlines() == ["carol", "dan"]
    assert "locked=true\n" in (host["etc"] / "people/dan.conf").read_text()


def test_remove_accepts_recorded_sync_commits_and_rotated_signers(memory_host, monkeypatch, capsys):
    """Prevent sync state written to a project record from blocking project removal, while add keeps its initial lines."""
    host = memory_host
    second_wire = KEY_WIRE[:19] + bytes(reversed(range(32)))
    second_key = "ssh-ed25519 " + base64.b64encode(second_wire).decode("ascii")
    assert project(host, monkeypatch, capsys, "add", "alpha", "alice", "--signed-by", KEY)[0] == 0
    record = host["etc"] / "projects/alpha.conf"
    assert record.read_text() == f"admin=alice\nsigned_by={KEY}\npublisher=porelo-publisher-alpha\n"
    record.write_text(
        record.read_text()
        + f"commit={'1' * 40}\n"
        + f"access_commit={'2' * 40}\n"
        + f"signer={KEY}\n"
        + f"signer={second_key}\n"
    )
    record.chmod(0o600)
    code, out, err = project(host, monkeypatch, capsys, "remove", "alpha")
    assert code == 0, (code, out, err)
    assert json.loads(out) == {"project": "alpha", "removed": True, "locked": []}
    assert not record.exists()


@pytest.mark.parametrize(
    "extra",
    [
        f"commit={'1' * 40}\n",
        f"commit={'1' * 40}\naccess_commit={'2' * 40}\n",
        f"signer={KEY}\n",
        f"commit=not-a-commit\naccess_commit={'2' * 40}\nsigner={KEY}\n",
        f"commit={'1' * 40}\naccess_commit=UPPER{'2' * 35}\nsigner={KEY}\n",
        f"commit={'1' * 40}\naccess_commit={'2' * 40}\nsigner=not-a-key\n",
        f"commit={'1' * 40}\naccess_commit={'2' * 40}\nsigner={KEY}\nsigner={KEY}\n",
        f"commit={'1' * 40}\ncommit={'3' * 40}\naccess_commit={'2' * 40}\nsigner={KEY}\n",
        f"commit={'1' * 40}\naccess_commit={'2' * 40}\nsigner={KEY}\nextra=unexpected\n",
    ],
    ids=[
        "commit-only",
        "missing-signer",
        "signer-only",
        "bad-commit",
        "bad-access-commit",
        "bad-signer",
        "duplicate-signer",
        "duplicate-commit",
        "unknown-field",
    ],
)
def test_remove_refuses_incomplete_duplicate_or_malformed_sync_lines(memory_host, monkeypatch, capsys, extra):
    """Prevent a half-written or tampered sync state in a project record from authorizing project deletion."""
    host = memory_host
    assert project(host, monkeypatch, capsys, "add", "alpha", "alice", "--signed-by", KEY)[0] == 0
    record = host["etc"] / "projects/alpha.conf"
    record.write_text(record.read_text() + extra)
    record.chmod(0o600)
    host["forge"].calls.clear()
    host["cli_calls"].clear()
    code, out, err = project(host, monkeypatch, capsys, "remove", "alpha")
    assert code == 65 and not out and err.startswith("porelo-host-project: "), (code, out, err)
    assert not host["forge"].calls
    assert record.exists()
