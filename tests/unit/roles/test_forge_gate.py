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
        "/user/settings/account/../applications",
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
    assert response.startswith(b"HTTP/1.1 401") and calls == []


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
