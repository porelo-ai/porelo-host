"""Prevent a push to the host's forge from passing unjudged, or the judge from answering anyone but the forge."""

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
HOOK = ROOT / "roles/forge/files/porelo-forge-pre-receive"
FORGE = ROOT / "roles/forge"


def run_hook(tmp_path, status, answer="porelo: 1 new commit(s) judged and recorded\n", fails=False):
    """The hook in a repository directory, with a curl that keeps what it was sent and answers as told."""
    stubs = tmp_path / "bin"
    stubs.mkdir()
    sent = tmp_path / "sent"
    curl = stubs / "curl"
    curl.write_text(
        f"#!{sys.executable}\n"
        "import pathlib, sys\n"
        f"pathlib.Path({str(sent)!r}).write_bytes(sys.stdin.buffer.read())\n"
        f"pathlib.Path({str(tmp_path / 'argv')!r}).write_text('\\n'.join(sys.argv[1:]))\n"
        + ("sys.exit(7)\n" if fails else f"sys.stdout.write({answer!r} + '{status}')\n")
    )
    curl.chmod(0o755)
    repository = tmp_path / "app.git"
    repository.mkdir()
    result = subprocess.run(
        ["/bin/sh", str(HOOK)],
        cwd=repository,
        input="a" * 40 + " " + "c" * 40 + " refs/heads/main\n",
        capture_output=True,
        text=True,
        env={
            "PATH": f"{stubs}:/usr/bin:/bin",
            "GIT_QUARANTINE_PATH": f"{repository}/objects/incoming-x",
            "GIT_OBJECT_DIRECTORY": f"{repository}/objects/incoming-x",
            "GIT_ALTERNATE_OBJECT_DIRECTORIES": f"{repository}/objects",
            "GITEA_PUSHER_NAME": "porelo-alice",
        },
        check=False,
    )
    return result, repository, sent.read_text() if sent.exists() else None, tmp_path / "argv"


def test_the_hook_sends_the_push_and_its_quarantine_and_takes_only_200(tmp_path):
    result, repository, sent, argv = run_hook(tmp_path, 200)
    assert result.returncode == 0, result.stderr
    assert result.stderr == "porelo: 1 new commit(s) judged and recorded\n"
    assert sent == (
        f"repository {repository}\nquarantine {repository}/objects/incoming-x\n"
        f"objects {repository}/objects/incoming-x\nalternates {repository}/objects\n"
        "pusher porelo-alice\n\n" + "a" * 40 + " " + "c" * 40 + " refs/heads/main\n"
    )
    arguments = argv.read_text().splitlines()
    assert arguments[arguments.index("--unix-socket") + 1] == "/run/porelo-verify/verify.sock"
    assert arguments[-1] == "http://localhost/verify"


@pytest.mark.parametrize("status", [403, 500, 302])
def test_the_hook_refuses_every_other_answer_and_shows_it(tmp_path, status):
    result, _, _, _ = run_hook(tmp_path, status, "porelo: refused\n")
    assert result.returncode != 0
    assert result.stderr == "porelo: refused\n"


def test_a_host_that_does_not_answer_refuses_the_push(tmp_path):
    result, _, _, _ = run_hook(tmp_path, 200, fails=True)
    assert result.returncode != 0
    assert result.stderr == "porelo: the host could not judge this push\n"


def test_the_forge_mounts_the_hook_and_the_judge_s_socket_read_only():
    container = (FORGE / "templates/forgejo.container.j2").read_text()
    assert "Volume=/usr/local/libexec/porelo/pre-receive:{{ __forge_push_hook }}:ro" in container
    assert "Volume=/run/porelo-host/verify:/run/porelo-verify:ro" in container


def test_the_host_program_judges_each_push_behind_its_socket_before_forgejo_starts():
    tasks = yaml.safe_load((FORGE / "tasks/service.yml").read_text())
    names = [task["name"] for task in tasks]
    assert names.index("service | Listen for the forge's pushes before Forgejo starts") < names.index(
        "service | Write Forgejo's quadlet unit"
    )
    socket = (FORGE / "templates/porelo-host-verify.socket.j2").read_text()
    assert "ListenStream=/run/porelo-host/verify/verify.sock\n" in socket and "Accept=yes\n" in socket
    service = (FORGE / "templates/porelo-host-verify@.service.j2").read_text()
    assert "ExecStart=/usr/sbin/porelo-host judge-push\n" in service, "a push must be judged by the host program"
    main = yaml.safe_load((FORGE / "tasks/main.yml").read_text())
    assert not any("ansible.builtin.fail" in task for task in main), "a host with the judge sets its forge up"
    install = yaml.safe_load((ROOT / "roles/porelo/tasks/install.yml").read_text())
    assert not any("ansible.builtin.fail" in task for task in install), "an upgrade with the judge migrates the forge"
    assert "StandardInput=socket\n" in service and "StandardOutput=socket\n" in service
    assert "User=" not in service, "the helper runs as root and answers only the forge account's peer"
    assert "RuntimeMaxSec=310\n" in service, "a judge that hangs holds its connection for ever"
    assert "SocketUser={{ forge_account }}\n" in socket and "SocketMode=0600\n" in socket, "anyone may connect"
    assert "MaxConnections=16\n" in socket


def test_a_new_hook_reaches_forgejo_and_its_directory_is_made_first():
    tasks = yaml.safe_load((FORGE / "tasks/service.yml").read_text())
    by_name = {task["name"]: task for task in tasks}
    names = list(by_name)
    install = by_name["service | Install the hook that has the host judge each push"]
    assert install["notify"] == "Restart Forgejo", "Forgejo's container keeps the hook it mounted at its start"
    directory = by_name["service | Make the directory of the gate and of the push hook"]
    assert directory["ansible.builtin.file"]["path"] == "/usr/local/libexec/porelo"
    assert names.index(directory["name"]) < names.index(install["name"])


def test_down_takes_the_judge_its_hook_and_its_records_away():
    down = (FORGE / "tasks/down.yml").read_text()
    for name in (
        "porelo-host-verify.socket",
        "porelo-host-verify@.service",
        "porelo-host-verify@*.service",
        "/usr/local/libexec/porelo-forge-pre-receive",
        "/var/lib/porelo-host/arrivals",
    ):
        assert name in down, name


def test_the_judge_s_socket_restarts_before_forgejo_and_its_directory_is_made_once():
    handlers = [handler["name"] for handler in yaml.safe_load((FORGE / "handlers/main.yml").read_text())]
    assert handlers.index("Restart the push judge's socket") < handlers.index("Restart Forgejo")
    tasks = yaml.safe_load((FORGE / "tasks/service.yml").read_text())
    made = [task for task in tasks if task.get("ansible.builtin.file", {}).get("path") == "/usr/local/libexec/porelo"]
    assert len(made) == 1
