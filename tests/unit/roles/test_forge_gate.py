"""Prevent forged browser identities, credential bypasses, and untracked credentials."""

import importlib.machinery
import importlib.util
import io
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def gate(monkeypatch):
    loader = importlib.machinery.SourceFileLoader("forge_gate", str(ROOT / "roles/forge/files/porelo-forge-gate"))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    monkeypatch.setattr(
        module.pwd,
        "getpwuid",
        lambda uid: SimpleNamespace(pw_name="person", pw_uid=uid, pw_gid=1000, pw_shell="/bin/bash"),
    )
    monkeypatch.setattr(module.grp, "getgrnam", lambda name: SimpleNamespace(gr_gid=2000, gr_mem=["person"]))
    return module


def request(gate, mode="web", uid=1000, path="/", headers=(), method="GET", body=b"", chunked=False):
    calls = []

    class Upstream:
        def request(self, method, path, body, headers, **kwargs):
            if hasattr(body, "read"):
                chunks = []
                while chunk := body.read(8192):
                    chunks.append(chunk)
                body = b"".join(chunks)
            calls.append((method, path, body, headers))

        def getresponse(self):
            return SimpleNamespace(
                status=200, reason="OK", getheaders=lambda: [("Content-Length", "2")], read=io.BytesIO(b"ok").read
            )

        def close(self):
            pass

    class Connection:
        def makefile(self, *args, **kwargs):
            return io.BytesIO(
                (
                    f"{method} {path} HTTP/1.1\r\nHost: host.localhost\r\n"
                    + "".join(f"{key}: {value}\r\n" for key, value in headers)
                    + ("\r\n" if chunked else f"Content-Length: {len(body)}\r\n\r\n")
                ).encode()
                + body
            )

        def sendall(self, data):
            output.write(data)

    output = io.BytesIO()
    gate.Handler(Connection(), ("local", 0), SimpleNamespace(mode=mode, uid=uid, upstream=Upstream))
    return output.getvalue(), calls


@pytest.mark.parametrize("mode", ["web", "git"])
def test_caller_identity_headers_never_reach_upstream(gate, mode):
    response, calls = request(
        gate,
        mode,
        headers=[
            ("x-WebAuth-User", "intruder"),
            ("X-WEBAUTH-Email", "intruder@example.org"),
            ("Authorization", "token fixture"),
        ],
    )
    assert response.startswith(b"HTTP/1.1 200")
    assert not any(key.lower().startswith("x-webauth-") for key in calls[0][3])


def test_browser_gets_only_the_peer_login(gate):
    _, calls = request(gate, headers=[("X-WEBAUTH-USER", "intruder")])
    assert calls[0][3]["X-WEBAUTH-USER"] == "person"


@pytest.mark.parametrize(
    "uid,shell,member",
    [(0, "/bin/bash", True), (999, "/bin/bash", True), (1000, "/usr/sbin/nologin", True), (1000, "/bin/bash", False)],
)
def test_root_service_and_unadmitted_callers_are_refused(gate, monkeypatch, uid, shell, member):
    monkeypatch.setattr(
        gate.pwd, "getpwuid", lambda value: SimpleNamespace(pw_name="person", pw_uid=value, pw_gid=1000, pw_shell=shell)
    )
    monkeypatch.setattr(
        gate.grp, "getgrnam", lambda name: SimpleNamespace(gr_gid=2000, gr_mem=["person"] if member else [])
    )
    response, calls = request(gate, uid=uid)
    assert response.startswith(b"HTTP/1.1 403")
    assert calls == []


@pytest.mark.parametrize(
    "path",
    [
        "/user/settings/account",
        "/user/settings/applications?tab=tokens",
        "/user/settings/%61pplications",
        "/api/v1/users/person/tokens",
        "/api/v1/user",
        "/api/v1/admin/users/person",
        "/user/forgot_password",
        "/user/reset_password",
        "/user/change_password",
        "/admin/users/1",
    ],
)
def test_browser_cannot_set_passwords_or_mint_tokens(gate, path):
    response, calls = request(gate, path=path, method="POST")
    assert response.startswith(b"HTTP/1.1 403")
    assert calls == []


MINTING = [
    ("/api/v1/users/person/tokens", "POST"),
    ("/api/v1/users/person/TOKENS", "POST"),
    ("/api/v1/users/person/tokens/7", "DELETE"),
    ("/login/oauth/authorize?client_id=fixture", "GET"),
    ("/login/oauth/grant", "POST"),
    ("/login/oauth/access_token", "POST"),
    ("/login/%6fauth/access_token", "POST"),
    ("/user/recover_account", "GET"),
    ("/user/recover_account/", "POST"),
    ("/user/settings/applications", "POST"),
    ("/api/v1/orgs/project/actions/runners/registration-token", "GET"),
    ("/api/v1/repos/project/repo/actions/runners/registration-token", "GET"),
    ("/api/v1/repos/project/repo/actions/runners", "GET"),
    ("/api/v1/admin/runners/registration-token", "GET"),
    ("/api/v1/user/actions/runners", "POST"),
    ("/api/v1/admin/actions/runners", "POST"),
    ("/api/v1/admin/users/person", "PATCH"),
    ("/org/project/settings/actions/runners", "GET"),
    ("/org/project/settings/actions/runners/new", "POST"),
    ("/org/project/settings/actions/runners/1/edit", "POST"),
    ("/project/repo/settings/actions/runners/reset_registration_token", "GET"),
    ("/admin/actions/runners/new", "GET"),
    ("/api/v1/admin/users", "POST"),
    ("/api/v1/user", "PATCH"),
    ("/user/forgot_password", "POST"),
    ("/user/reset_password", "POST"),
    ("/user/change_password", "POST"),
    ("/admin/users/1", "POST"),
    ("/api/v1/users/person%2fx/tokens", "POST"),
]


@pytest.mark.parametrize("mode", ["web", "git", "runner"])
@pytest.mark.parametrize("credential", [None, "token fixture"])
@pytest.mark.parametrize("path, method", MINTING)
def test_no_caller_gets_a_forge_credential_through_any_socket(gate, mode, credential, path, method):
    """Prevent a token, an OAuth2 grant, a runner's registration or a password made past the host."""
    headers = [] if credential is None else [("Authorization", credential)]
    response, calls = request(gate, mode, path=path, method=method, headers=headers)
    assert response.startswith(b"HTTP/1.1 403")
    assert calls == []


@pytest.mark.parametrize("mode", ["web", "git", "runner"])
@pytest.mark.parametrize(
    "path",
    [
        "/%2fuser/recover_account",
        "/api/v1/users/person/tokens/..%2ffixture",
        "/api/v1/users/person/x/%2e%2e/tokens",
        "/project/repo/./settings/actions/runners",
        "/api/v1/users/person%2f%2ftokens",
        "/api/v1/user%2f",
        "/project/repo%2f%2e%2e/settings",
        "/api/v1/users/person%2fx^/tokens",
        "/api/packages/project/generic/pkg/1.0/a%2f{b}",
        "/project/repo%2fx|/info/refs",
        "/project/repo/src/%zz",
        "/api/v1/users/alice/tokens/tok%0a",
        "/api/v1/users/alice/tokens/tok%0D",
        "/project/repo/info/lfs/objects/0123/file%0a",
        "/api/packages/project/maven/com/example/app%09/1.0/app-1.0.jar",
        "/v2/token%0a",
        "/api/v1/users/alice/tokens/tok%00",
        "/api/v1/users/alice/tokens/tok%7f",
    ],
)
def test_a_path_read_differently_by_forgejo_is_refused(gate, mode, path):
    """Prevent an encoded slash or a dot segment taking a refused route past the gate's match."""
    response, calls = request(gate, mode, path=path, method="POST", headers=[("Authorization", "token fixture")])
    assert response.startswith(b"HTTP/1.1 400")
    assert calls == []


@pytest.mark.parametrize("mode", ["web", "git"])
def test_the_runners_own_protocol_is_the_runner_sockets_alone(gate, mode):
    """Prevent a runner registered through a person's socket; the host's runner registers through runner.sock."""
    register = "/api/actions/runner.v1.RunnerService/Register"
    response, calls = request(gate, mode, path=register, method="POST", headers=[("Authorization", "token fixture")])
    assert response.startswith(b"HTTP/1.1 403") and calls == []
    response, calls = request(gate, "runner", path=register, method="POST")
    assert response.startswith(b"HTTP/1.1 200") and calls[0][1] == register


@pytest.mark.parametrize(
    "path",
    [
        "/v2/project/image/manifests/1",
        "/api/packages/project/generic/pkg/1.0/file",
        "/project/repo.git/info/refs?service=git-receive-pack",
        "/project/repo/git-upload-pack",
        "/project/repo.git/info/lfs/objects/batch",
        "/project/repo.git/HEAD",
        "/project/repo.git/objects/info/packs",
        "/project/repo%2fx/info/refs",
    ],
)
def test_the_browser_gets_git_and_packages_only_with_a_token(gate, path):
    """Prevent Forgejo taking the gate's sign-in for Git, LFS or packages, yet pass the token their links under
    ROOT_URL bring to web.sock."""
    response, calls = request(gate, path=path, method="POST")
    assert response.startswith(b"HTTP/1.1 401") and b"WWW-Authenticate: Basic" in response
    assert calls == []
    response, calls = request(gate, path=path, method="POST", headers=[("Sec-Fetch-Mode", "navigate")])
    assert response.startswith(b"HTTP/1.1 403") and b"WWW-Authenticate" not in response
    assert calls == []
    for mode in ("web", "git"):
        response, calls = request(gate, mode, path=path, method="POST", headers=[("Authorization", "token fixture")])
        assert response.startswith(b"HTTP/1.1 200") and calls[0][1] == path, mode
        assert "x-webauth-user" not in {key.lower() for key in calls[0][3]}


@pytest.mark.parametrize(
    "pattern, path",
    [
        ("MINTING", "/api/v1/users/alice/tokens/a\nb"),
        ("TOKEN_EXCHANGE", "/v2/token/a\nb"),
        ("SIGNED_IN_ONLY_BY_TOKEN", "/api/packages/project/maven/a\nb"),
        ("SIGNED_IN_ONLY_BY_TOKEN", "/project/repo.git/info/lfs/objects/a\nb"),
    ],
)
def test_a_decoded_newline_never_ends_a_route_match(gate, pattern, path):
    """Prevent a byte the path check misses later from taking a refused route past its pattern."""
    assert getattr(gate, pattern).fullmatch(path)


@pytest.mark.parametrize("path", ["/user/avatar/head/72", "/user/avatar/objects/72", "/project/repo/src/branch/head"])
def test_pages_the_browser_shows_are_no_git_route(gate, path):
    """Prevent an avatar or a page of a person or repository named like a Git route being refused or challenged."""
    response, calls = request(gate, path=path)
    assert response.startswith(b"HTTP/1.1 200") and calls[0][1] == path


@pytest.mark.parametrize(
    "path",
    [
        "/api/packages/project/maven/org/example/lib/1.0-SNAPSHOT/maven-metadata.xml",
        "/project/repo.git/info/refs?service=git-upload-pack",
    ],
)
def test_the_browser_socket_challenges_a_client_that_waits_for_one(gate, path):
    """Prevent Maven or pip stopping at a refusal before they send their token to a link under ROOT_URL."""
    response, calls = request(gate, path=path)
    assert response.startswith(b"HTTP/1.1 401")
    assert b"WWW-Authenticate: Basic" in response
    assert calls == []


@pytest.mark.parametrize("mode", ["web", "git", "runner"])
@pytest.mark.parametrize(
    "path",
    ["/v2/token", "/v2/token?scope=repository:project/image:push", "/api/packages/person/conan/v2/users/authenticate"],
)
def test_no_token_is_exchanged_for_one_a_revocation_does_not_end(gate, mode, path):
    """Prevent a host-made token turned into a signed one Forgejo does not record, on any socket."""
    for headers in ([], [("Authorization", "token fixture")]):
        response, calls = request(gate, mode, path=path, headers=headers)
        assert response.startswith(b"HTTP/1.1 403") and calls == []


@pytest.mark.parametrize("mode", ["web", "git"])
@pytest.mark.parametrize(
    "path",
    [
        "/project/repo/src/branch/main/src/tokens/Store.java",
        "/project/repo/src/branch/main/src/runners/new",
        "/project/repo/src/branch/main/settings/actions/runners.md",
        "/api/v1/repos/project/repo/contents/src/tokens/Store.java",
        "/api/v1/repos/project/tokens",
        "/api/v1/repos/project/repo/branches/tokens",
        "/api/v1/user",
        "/api/v1/repos/project/repo/branches/porelo%2Ftask",
        "/project/repo/src/branch/main/a^b|c.txt",
    ],
)
def test_names_like_a_refused_route_elsewhere_still_pass(gate, mode, path):
    """Prevent a repository, branch or file named tokens or runners being refused as if it were a credential route."""
    headers = [] if mode == "web" else [("Authorization", "token fixture")]
    response, calls = request(gate, mode, path=path, headers=headers)
    assert response.startswith(b"HTTP/1.1 200")
    assert calls[0][1] == path


def test_git_challenges_before_any_upstream_request(gate):
    response, calls = request(gate, "git", headers=[("Cookie", "session=fixture")])
    assert response.startswith(b"HTTP/1.1 401")
    assert b"WWW-Authenticate: Basic" in response
    assert calls == []


@pytest.mark.parametrize("credential", ["Basic cGVyc29uOmZpeHR1cmU=", "token fixture"])
def test_git_forwards_credentials_and_body_but_no_cookie(gate, credential):
    response, calls = request(
        gate,
        "git",
        path="/owner/repo.git/git-receive-pack",
        method="POST",
        body=b"git body",
        headers=[("Cookie", "session=fixture"), ("Authorization", credential)],
    )
    assert response.startswith(b"HTTP/1.1 200")
    assert calls[0][2] == b"git body"
    assert calls[0][3]["Authorization"] == credential
    assert "cookie" not in {key.lower() for key in calls[0][3]}


def test_ambiguous_framing_is_refused_before_forwarding(gate):
    response, calls = request(gate, headers=[("Transfer-Encoding", "chunked")])
    assert response.startswith(b"HTTP/1.1 400")
    assert calls == []


def test_git_accepts_chunked_push_without_buffering_the_pack(gate):
    _, calls = request(
        gate,
        "git",
        method="POST",
        body=b"1\r\ng\r\n2\r\nit\r\n0\r\n\r\n",
        headers=[("Authorization", "token fixture"), ("Transfer-Encoding", "chunked")],
        chunked=True,
    )
    assert calls[0][2] == b"git"


def test_unknown_peer_is_refused(gate, monkeypatch):
    def unknown(uid):
        raise KeyError(uid)

    monkeypatch.setattr(gate.pwd, "getpwuid", unknown)
    response, calls = request(gate)
    assert response.startswith(b"HTTP/1.1 403")
    assert calls == []


def test_primary_group_membership_is_admitted(gate, monkeypatch):
    monkeypatch.setattr(gate.grp, "getgrnam", lambda name: SimpleNamespace(gr_gid=1000, gr_mem=[]))
    response, calls = request(gate)
    assert response.startswith(b"HTTP/1.1 200")
    assert calls[0][3]["X-WEBAUTH-USER"] == "person"


def test_connection_header_cannot_remove_git_credentials(gate):
    response, calls = request(
        gate, "git", headers=[("Authorization", "token fixture"), ("Connection", "Authorization")]
    )
    assert response.startswith(b"HTTP/1.1 400")
    assert calls == []


@pytest.mark.parametrize("body", [b"3\r\ngitXX0\r\n\r\n", b"3\r\ngit\r\n0\r\nTrailer: no\r\n\r\n", b"3\r\ngi"])
def test_incomplete_or_ambiguous_chunked_requests_fail_closed(gate, body):
    response, _ = request(
        gate,
        "git",
        method="POST",
        body=body,
        headers=[("Authorization", "token fixture"), ("Transfer-Encoding", "chunked")],
        chunked=True,
    )
    assert response.startswith(b"HTTP/1.1 502")


def test_host_card_names_the_distinct_local_gate_ports():
    """Prevent clients from forwarding token-bearing Git requests to the browser gate."""
    import yaml
    from jinja2.nativetypes import NativeEnvironment

    tasks = yaml.safe_load((ROOT / "roles/base/tasks/host.yml").read_text())
    host = next(
        task["ansible.builtin.set_fact"]["__base_host"]
        for task in tasks
        if "__base_host" in task.get("ansible.builtin.set_fact", {})
    )
    environment = NativeEnvironment()
    environment.filters["bool"] = bool
    template = environment.from_string(host["services"])
    assert template.render(porelo_host_forge=True, forge_http_port=3100, forge_git_port=3101) == {
        "forge": {"web_port": 3100, "git_port": 3101}
    }
    assert template.render(porelo_host_forge=False) == {}


def test_runner_protocol_passes_without_a_token_but_nothing_else_does(gate):
    """Prevent the runner's own protocol being refused, or its exemption opening any other route without a token."""
    ping = "/api/actions/ping.v1.PingService/Ping"
    response, calls = request(
        gate, "runner", path=ping, method="POST", headers=[("x-runner-uuid", "fixture"), ("Cookie", "s=fixture")]
    )
    assert response.startswith(b"HTTP/1.1 200")
    assert calls[0][1] == ping and calls[0][3]["x-runner-uuid"] == "fixture"
    assert "cookie" not in {key.lower() for key in calls[0][3]}
    for path in (
        "/api/v1/user",
        "/owner/repo.git/info/refs",
        "/api/actions/../v1/user",
        "/api/actions/%2e%2e/v1/user",
        "/api/actionsx/ping",
        "/api/actions/",
    ):
        response, calls = request(gate, "runner", path=path)
        assert response.startswith((b"HTTP/1.1 401", b"HTTP/1.1 400")) and calls == [], path
    response, calls = request(gate, "git", path=ping, method="POST")
    assert response.startswith(b"HTTP/1.1 403") and calls == []


def test_runner_forwards_job_tokens_as_git_does(gate):
    """Prevent a job's checkout token failing on the runner's path."""
    response, calls = request(gate, "runner", path="/owner/repo.git/info/refs", headers=[("Authorization", "token t")])
    assert response.startswith(b"HTTP/1.1 200") and calls[0][3]["Authorization"] == "token t"


def test_runner_forwards_a_jobs_bearer_token_but_git_does_not(gate):
    """Prevent a job's artifact calls failing, without widening the Git socket's credentials."""
    path = "/api/actions_pipeline/_apis/pipelines/workflows/1/artifacts"
    response, calls = request(gate, "runner", path=path, headers=[("Authorization", "Bearer job.fixture-token")])
    assert response.startswith(b"HTTP/1.1 200") and calls[0][3]["Authorization"] == "Bearer job.fixture-token"
    response, calls = request(gate, "git", path=path, headers=[("Authorization", "Bearer job.fixture-token")])
    assert response.startswith(b"HTTP/1.1 401") and calls == []


def test_host_card_names_no_certificate_authority():
    """Prevent up failing on, or the summary naming, a host CA that SSH-only access no longer makes."""
    text = (ROOT / "roles/base/tasks/host.yml").read_text()
    assert "ca_sha256" not in text and "base_ca_path" not in text
    assert "base_ca_path" not in (ROOT / "roles/base/defaults/main.yml").read_text()


def test_forgejo_offers_no_oauth2_grant():
    """Prevent a signed-in person granting themselves a lasting token through Forgejo's built-in OAuth2 apps."""
    lines = (ROOT / "roles/forge/templates/forgejo.container.j2").read_text().splitlines()
    assert "Environment=FORGEJO__oauth2__ENABLED=false" in lines
    assert not [line for line in lines if "FORGEJO__oauth2__ENABLE" in line and not line.endswith("=false")]


def loopback_gate(mode, request_bytes):
    """Run the gate on one accepted loopback TCP connection, as the socket's ListenStream=127.0.0.1 hands it over."""
    import os
    import socket
    import subprocess
    import sys

    with socket.create_server(("127.0.0.1", 0)) as listener:
        client = socket.create_connection(listener.getsockname())
        accepted, _ = listener.accept()
    with client, accepted:
        fd = accepted.fileno()
        gate = subprocess.Popen(
            [
                sys.executable,
                "-I",
                str(ROOT / "roles/forge/files/porelo-forge-gate"),
                f"--{mode}",
                "--upstream",
                "/nonexistent/forgejo.sock",
            ],
            pass_fds=(fd, 3),
            preexec_fn=lambda: os.dup2(fd, 3),
            stdin=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        accepted.close()
        client.settimeout(10)
        answer = b""
        try:
            client.sendall(request_bytes)
            client.shutdown(socket.SHUT_WR)
            while chunk := client.recv(65536):
                answer += chunk
        except OSError:
            pass  # A gate that closed before or on the request resets the connection, which is a refusal too.
        _, stderr = gate.communicate(timeout=10)
    return gate.returncode, answer, stderr


def test_git_on_loopback_tcp_challenges_without_reading_a_peer():
    """Prevent the loopback port from answering anything but the token challenge to a request without a token."""
    code, answer, stderr = loopback_gate("git", b"GET /porelo/stand-in.git/info/refs HTTP/1.1\r\nHost: x\r\n\r\n")
    assert answer.startswith(b"HTTP/1.1 401"), (answer, stderr)
    assert b"WWW-Authenticate: Basic" in answer
    assert code == 0, stderr


@pytest.mark.parametrize("mode", ["web", "runner"])
def test_peer_checked_modes_refuse_a_tcp_connection(mode):
    """Prevent the browser's or runner's gate, which trust the peer's socket, from serving a TCP connection."""
    code, answer, stderr = loopback_gate(mode, b"GET / HTTP/1.1\r\nHost: x\r\n\r\n")
    assert answer == b"" and code != 0
    assert f"{mode} mode serves a Unix socket alone".encode() in stderr
