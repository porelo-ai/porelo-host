"""Guard the move's read-only check and the room's tunnel against saying more than they saw."""

import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "build/move-check.sh"
TUNNEL = ROOT / "build/room-tunnel.sh"

GOOD = {
    "status": json.dumps({"name": "t1", "running": True, "project": "porelo", "repository": "sluice"}),
    "status_text": (
        "task       t1\nbranch     refs/porelo/incoming/t1\nforge      porelo/t1\n"
        "builds     forgejo\npull req   http://forge/pulls/7\nbuild      " + "a" * 12 + "  success since 1m\n"
    ),
    "build": json.dumps({"branch": "porelo/t1", "commit": "a" * 40, "verdict": "success"}),
    "build_code": "0",
    "log": (
        "AT                       EVENT        PEER                 MESSAGE                              DETAIL\n"
        "2026-11-06T10:00:00Z     taken        -                    m1.json                              -\n"
        "2026-11-06T10:00:01Z     sent         -                    m1.json                              matrix\n"
    ),
    "heads": "ref: refs/heads/main\tHEAD\n" + "a" * 40 + "\trefs/heads/porelo/t1\n",
    "pulls": json.dumps([{"head": {"ref": "porelo/t1"}, "base": {"ref": "main"}}]),
    "pulls_next": "[]",
    "git_code": "0",
    "curl_code": "0",
    "credential_code": "0",
}

NO_BUILDS = "porelo: project 'porelo' has no builds: configuration; builds: needs security_class: online.\n"


def fake(path, name, body):
    command = path / name
    command.write_text("#!/bin/sh\n" + body)
    command.chmod(0o755)


@pytest.fixture
def porelo(tmp_path):
    """Stand-ins for Porelo, Git and curl, recording arguments so writes and credential leaks show."""

    def install(**answers):
        values = {**GOOD, **answers}
        log = tmp_path / "calls"
        for key, value in values.items():
            (tmp_path / key).write_text(value)
        (tmp_path / "forge.conf").write_text("host=forge.example\nname=forge.example\nport=3000\ngit_port=3022\n")
        fake(
            tmp_path,
            "porelo",
            f"""echo "$*" >> {log}
case "$1 $2 $*" in
    "task status "*--json*) cat {tmp_path}/status ;;
    "task status "*) cat {tmp_path}/status_text ;;
    "build status "*) code=$(cat {tmp_path}/build_code)
        cat {tmp_path}/build
        exit "$code" ;;
    "talk log "*) cat {tmp_path}/log ;;
    "vault credential "*) cat >/dev/null
        printf 'username=alice\\npassword=%s\\n\\n' "$MOVE_CHECK_TOKEN"
        exit "$(cat {tmp_path}/credential_code)" ;;
    *) echo "unexpected: $*" >&2; exit 99 ;;
esac
""",
        )
        fake(
            tmp_path,
            "git",
            f"""printf '%s\\n' "git $*" >> {log}
env | grep -q '^GIT_TERMINAL_PROMPT=0$' || exit 98
case " $* " in
    *" ls-remote "*) cat {tmp_path}/heads; exit "$(cat {tmp_path}/git_code)" ;;
    *) echo "unexpected: $*" >&2; exit 99 ;;
esac
""",
        )
        fake(
            tmp_path,
            "curl",
            f"""printf '%s\\n' "curl $*" >> {log}
case " $* " in
    *" -K - "*) python3 -Ic 'import os,sys
config = sys.stdin.read()
expected = "Authorization: token " + os.environ["MOVE_CHECK_TOKEN"]
sys.exit(0 if expected in config else 97)' || exit $? ;;
    *) exit 96 ;;
esac
[ "$(cat {tmp_path}/curl_code)" = 0 ] || exit "$(cat {tmp_path}/curl_code)"
[ ! -f {tmp_path}/pulls_endless ] || {{ cat {tmp_path}/pulls; exit 0; }}
case "$*" in
    *"/api/v1/repos/porelo/sluice/pulls?state=open"*)
        case "$*" in
            *"page=2"*) cat {tmp_path}/pulls_next ;;
            *"page=3"*) printf '[]' ;;
            *) cat {tmp_path}/pulls ;;
        esac ;;
    *) echo "unexpected: $*" >&2; exit 99 ;;
esac
""",
        )
        return log

    return install


def check(tmp_path, *arguments):
    environment = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "PORELO_HOST_FORGE_CONF": str(tmp_path / "forge.conf"),
        "MOVE_CHECK_TOKEN": "synthetic-person-token",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
    }
    # A check that loops must fail the test, not hold the suite.
    return subprocess.run(
        [str(CHECK), *arguments], capture_output=True, text=True, env=environment, check=False, timeout=30
    )


def test_every_line_holds_once_the_agent_has_moved(tmp_path, porelo):
    """Prevent the check staying red after a move that went right."""
    calls = porelo()
    done = check(tmp_path, "t1", "Agent Sluice", "--wake-answered")
    assert done.returncode == 0, done.stdout + done.stderr
    assert done.stdout.count("ok:") == 6 and "FAILED" not in done.stdout
    assert all(
        line.split()[0] in ("task", "build", "talk", "git", "vault", "curl") for line in calls.read_text().splitlines()
    )
    assert "--logs=none" in calls.read_text() and "--branch=porelo/t1" in calls.read_text()


def test_the_push_is_found_on_the_branch_the_gate_forwarded_it_to(tmp_path, porelo):
    """Prevent a push the gate forwarded to porelo/<task>-2 after an amend being missed on porelo/<task>."""
    calls = porelo(
        status_text=GOOD["status_text"].replace("a" * 12, "b" * 12),
        heads="ref: refs/heads/main\tHEAD\n"
        + "a" * 40
        + "\trefs/heads/porelo/t1\n"
        + "b" * 40
        + "\trefs/heads/porelo/t1-2\n",
        pulls=json.dumps([{"head": {"ref": "porelo/t1-2"}, "base": {"ref": "main"}}]),
        build=json.dumps({"branch": "porelo/t1-2", "commit": "b" * 40, "verdict": "success"}),
    )
    done = check(tmp_path, "t1", "Agent Sluice", "--wake-answered")
    assert done.returncode == 0, done.stdout + done.stderr
    assert any(line.startswith("ok:") and "as porelo/t1-2" in line for line in done.stdout.splitlines()), done.stdout
    assert "--branch=porelo/t1-2" in calls.read_text()


def test_the_latest_forward_of_the_push_is_named_when_several_hold_it(tmp_path, porelo):
    """Prevent the name order of the forge's branches picking an older forward of the same push."""
    calls = porelo(
        heads="ref: refs/heads/main\tHEAD\n"
        + "".join("a" * 40 + f"\trefs/heads/porelo/t1{tail}\n" for tail in ("", "-10", "-2", "x-3")),
        pulls=json.dumps([{"head": {"ref": "porelo/t1-10"}, "base": {"ref": "main"}}]),
        build=json.dumps({"branch": "porelo/t1-10", "commit": "a" * 40, "verdict": "success"}),
    )
    done = check(tmp_path, "t1", "Agent Sluice", "--wake-answered")
    assert any(line.startswith("ok:") and "as porelo/t1-10" in line for line in done.stdout.splitlines()), done.stdout
    assert "--branch=porelo/t1-10" in calls.read_text()


def test_a_repository_with_a_second_line_is_asked_of_nobody(tmp_path, porelo):
    """Prevent a second line in the task's repository reaching the forge or the build reader as a name that held."""
    calls = porelo(
        status=json.dumps({"name": "t1", "running": True, "project": "porelo", "repository": "sluice\n--evil"}),
    )
    done = check(tmp_path, "t1", "Agent Sluice", "--wake-answered")
    assert done.returncode == 1
    assert any(line.startswith("FAILED") and "cannot say" in line for line in done.stdout.splitlines()), done.stdout
    asked = calls.read_text()
    assert "ls-remote" not in asked and "build status" not in asked, asked


def test_a_project_without_builds_names_the_reader_not_configured(tmp_path, porelo):
    """Prevent a guarded move failing because build monitoring never recorded its existing forge push and PR."""
    calls = porelo(
        status_text="task       t1\nforge      porelo/t1\n",
        build=NO_BUILDS,
        build_code="78",
    )
    done = check(tmp_path, "t1", "Agent Sluice", "--wake-answered")
    assert done.returncode == 0, done.stdout + done.stderr
    lines = done.stdout.splitlines()
    assert len(lines) == 6 and "FAILED" not in done.stdout, "each move fact holds without build monitoring"
    assert any("Build" in line and "not configured: the project has no builds:" in line for line in lines)
    assert any(line.startswith("ok:") and "a" * 40 in line and "last push" in line for line in lines)
    assert any(line.startswith("ok:") and "pull request" in line for line in lines)
    assert "curl " in calls.read_text(), "the PR is read from the forge"


def test_a_task_that_sent_into_its_conversation_has_joined_it(tmp_path, porelo):
    """Prevent the conversation line asking talk peers, which never lists a project's own tasks."""
    calls = porelo()
    done = check(tmp_path, "t1", "Agent Sluice", "--wake-answered")
    assert any(line.startswith("ok:") and "conversation" in line for line in done.stdout.splitlines()), done.stdout
    assert "talk log t1" in calls.read_text() and "talk peers" not in calls.read_text()


def test_the_forge_is_read_with_the_persons_vault_answering_git_and_no_token_in_an_argument(tmp_path, porelo):
    """Prevent a token on a command line, and a check that makes the person's forge token anew."""
    calls = porelo()
    done = check(tmp_path, "t1", "Agent Sluice", "--wake-answered")
    assert done.returncode == 0, done.stdout + done.stderr
    git = [line for line in calls.read_text().splitlines() if line.startswith("git ")]
    assert len(git) == 1 and "http://127.0.0.1:3022/porelo/sluice.git" in git[0] and "@" not in git[0]
    assert "--symref" in git[0] and "--heads" not in git[0], "Git must also advertise the default branch"
    assert "credential.http://127.0.0.1:3022.helper=!porelo vault credential --entry forge.example.person" in git[0]
    asked = calls.read_text()
    assert any(line.startswith("curl ") for line in asked.splitlines()), "the API also uses the person's credential"
    assert "vault credential --entry forge.example.person" in asked
    assert "synthetic-person-token" not in asked, "no fake receives the credential in its argument list"
    assert "synthetic-person-token" not in done.stdout + done.stderr, "the credential stays out of check output"
    assert "forge-token" not in asked and "sudo" not in asked


@pytest.mark.parametrize(
    "answers, named",
    [
        (dict(status=json.dumps({"name": "t1", "state": "absent", "running": False})), "the task runs"),
        (dict(heads="ref: refs/heads/main\tHEAD\n"), "last push"),
        (dict(heads="a" * 40 + "\trefs/heads/porelo/t10\n"), "last push"),
        (dict(status_text="task       t1\npull req   http://forge/pulls/7\n"), "last push"),
        (dict(build=json.dumps({"branch": "porelo/t1", "commit": "a" * 40, "verdict": "unknown"})), "Build"),
        # A Build the reader holds of an earlier commit on the branch is not one of this push.
        (dict(build=json.dumps({"branch": "porelo/t1", "commit": "c" * 40, "verdict": "success"})), "Build"),
        # HEAD naming no branch gives the pull request no base to be asked against.
        (
            dict(
                heads="ref: refs/tags/v1\tHEAD\n" + "a" * 40 + "\trefs/heads/porelo/t1\n",
                pulls=json.dumps([{"head": {"ref": "porelo/t1"}, "base": {"ref": "refs/tags/v1"}}]),
            ),
            "pull request",
        ),
        (dict(pulls="[]"), "pull request"),
        (dict(log=GOOD["log"].replace("matrix", "local")), "conversation"),
    ],
)
def test_each_line_fails_by_name(tmp_path, porelo, answers, named):
    """Prevent a move passing with one of the procedure's facts missing, or a failure naming nothing."""
    porelo(**answers)
    done = check(tmp_path, "t1", "Agent Sluice", "--wake-answered")
    assert done.returncode == 1
    assert any(line.startswith("FAILED") and named in line for line in done.stdout.splitlines()), done.stdout


@pytest.mark.parametrize(
    "pulls",
    [
        [{"head": {"ref": "porelo/t10"}, "base": {"ref": "main"}}],
        [{"head": {"ref": "porelo/t1"}, "base": {"ref": "release"}}],
    ],
)
def test_a_pull_request_for_another_head_or_base_does_not_count(tmp_path, porelo, pulls):
    """Prevent another task's or another target branch's review being accepted as this move's review."""
    porelo(pulls=json.dumps(pulls))
    done = check(tmp_path, "t1", "Agent Sluice", "--wake-answered")
    assert done.returncode == 1
    assert any(line.startswith("FAILED") and "pull request" in line for line in done.stdout.splitlines()), done.stdout


def test_the_pull_request_targets_the_repositorys_actual_default_branch(tmp_path, porelo):
    """Prevent a move requiring review on main when the forge's default branch has another name."""
    porelo(
        heads=GOOD["heads"].replace("refs/heads/main", "refs/heads/trunk"),
        pulls=json.dumps([{"head": {"ref": "porelo/t1"}, "base": {"ref": "trunk"}}]),
        status_text="task       t1\nforge      porelo/t1\n",
    )
    done = check(tmp_path, "t1", "Agent Sluice", "--wake-answered")
    assert done.returncode == 0, done.stdout + done.stderr


def test_the_pull_request_can_be_on_a_later_page(tmp_path, porelo):
    """Prevent a reviewed move failing just because other open requests fill the first API page."""
    calls = porelo(
        pulls=json.dumps([{"head": {"ref": "another-task"}, "base": {"ref": "main"}}]),
        pulls_next=GOOD["pulls"],
        status_text="task       t1\nforge      porelo/t1\n",
    )
    done = check(tmp_path, "t1", "Agent Sluice", "--wake-answered")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "page=2" in calls.read_text(), "the next page is read before declaring the PR missing"


def test_a_forge_that_never_ends_its_pages_fails_the_line(tmp_path, porelo):
    """Prevent a forge that answers every page with requests from holding the check forever."""
    porelo(pulls=json.dumps([{"head": {"ref": "another-task"}, "base": {"ref": "main"}}]))
    (tmp_path / "pulls_endless").write_text("")
    done = check(tmp_path, "t1", "Agent Sluice", "--wake-answered")
    assert done.returncode == 1, done.stdout + done.stderr
    assert "pages" in done.stdout, done.stdout


@pytest.mark.parametrize("response", ["not JSON", "{}", "[{}]"])
def test_an_invalid_forge_response_cannot_count_as_review(tmp_path, porelo, response):
    """Prevent malformed forge evidence being accepted as an existing pull request."""
    porelo(pulls=response)
    done = check(tmp_path, "t1", "Agent Sluice", "--wake-answered")
    assert done.returncode == 1, done.stdout + done.stderr
    assert any(line.startswith("FAILED") and "pull request" in line for line in done.stdout.splitlines()), done.stdout


@pytest.mark.parametrize("failure", ["git_code", "curl_code", "credential_code", "build_code"])
def test_a_failed_reader_cannot_pass_with_plausible_output(tmp_path, porelo, failure):
    """Prevent unavailable forge evidence or a failed build reader being accepted as a checked move."""
    porelo(**{failure: "69"})
    done = check(tmp_path, "t1", "Agent Sluice", "--wake-answered")
    assert done.returncode == 1, done.stdout + done.stderr
    named = "Build" if failure == "build_code" else "last push" if failure == "git_code" else "pull request"
    assert any(line.startswith("FAILED") and named in line for line in done.stdout.splitlines()), done.stdout


def test_the_wake_counts_only_when_the_person_who_posted_says_so(tmp_path, porelo):
    """Prevent a read-only check claiming an answer it cannot have seen."""
    porelo()
    done = check(tmp_path, "t1", "Agent Sluice")
    assert done.returncode == 1
    assert "FAILED" in done.stdout and "wakes it" in done.stdout


def test_reading_a_failed_build_holds_this_line_as_the_moves_own_work_judges_the_verdict(tmp_path, porelo):
    """Prevent reading the Build being confused with the Build passing, which the move's own work judges."""
    porelo(build=json.dumps({"branch": "porelo/t1", "commit": "a" * 40, "verdict": "failure"}))
    assert check(tmp_path, "t1", "Agent Sluice", "--wake-answered").returncode == 0


def test_missing_arguments_are_refused(tmp_path, porelo):
    porelo()
    assert check(tmp_path).returncode == 64


def run_tunnel(tmp_path, *arguments):
    log = tmp_path / "ssh-calls"
    fake(tmp_path, "ssh", f'echo "$*" >> {log}\nexit 0\n')
    environment = {**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}", "ROOM_TUNNEL_ONCE": "1"}
    done = subprocess.run([str(TUNNEL), *arguments], capture_output=True, text=True, env=environment, check=False)
    return done, log.read_text() if log.exists() else ""


def test_the_tunnel_binds_one_socket_of_the_persons_own_to_the_homeservers_port(tmp_path):
    """Prevent the tunnel taking the window's return socket, a TCP listener, or a shell on the host."""
    done, calls = run_tunnel(tmp_path, "alice", "host.example", "8448")
    assert done.returncode == 0, done.stderr
    assert "-R /run/porelo-host/people/alice/room.sock:127.0.0.1:8448" in calls
    assert " -N " in f" {calls} " and "ExitOnForwardFailure=yes" in calls and "StreamLocalBindUnlink=yes" in calls
    assert "return.sock" not in calls and calls.rstrip().endswith("alice@host.example")
    assert done.stdout.strip() == "unix:/run/porelo-host/people/alice/room.sock"


@pytest.mark.parametrize(
    "arguments",
    [
        ("alice\nbad x", "room.example", "8448"),
        ("alice", "room.example\nbad x", "8448"),
        ("alice", "room.example", "8448\nx"),
    ],
)
def test_the_tunnel_refuses_a_value_with_a_second_line(tmp_path, arguments):
    """Prevent grep passing a value because one of its lines fits, the rest reaching ssh."""
    done, calls = run_tunnel(tmp_path, *arguments)
    assert done.returncode == 64 and not calls


@pytest.mark.parametrize(
    "arguments",
    [
        ("alice", "host.example"),
        ("Al/ice", "host.example", "8448"),
        ("alice", "-oProxyCommand=x", "8448"),
        ("alice", "host.example", "port"),
        ("alice", "host.example", "70000"),
    ],
)
def test_the_tunnel_refuses_what_could_become_an_option_or_a_path(tmp_path, arguments):
    """Prevent an argument turning into an ssh option or leaving the person's directory."""
    done, calls = run_tunnel(tmp_path, *arguments)
    assert done.returncode == 64 and not calls


REHEARSE = ROOT / "build/rehearse-move.sh"


def rehearsal(tmp_path, *, listed="", running=False):
    """The rehearsal script in a checkout of its own, with virsh and porelo-vm stood in for, each call recorded."""
    root = tmp_path / "checkout"
    (root / "build").mkdir(parents=True)
    (root / "roles/vm_pool/files").mkdir(parents=True)
    script = root / "build/rehearse-move.sh"
    script.write_bytes(REHEARSE.read_bytes())
    script.chmod(0o755)
    (root / "build/test-image").write_bytes((ROOT / "build/test-image").read_bytes())
    tunnel = root / "build/room-tunnel.sh"
    tunnel.write_bytes(TUNNEL.read_bytes())
    tunnel.chmod(0o755)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls"
    (tmp_path / "listed").write_text(listed)
    fake(
        bin_dir,
        "virsh",
        f"""echo "virsh $*" >> {log}
case "$1" in
    list) cat {tmp_path / "listed"} ;;
    vol-list) printf ' Name Path\\n----\\n' ;;
    domstate) {"echo running" if running else "echo 'shut off'"} ;;
esac
""",
    )
    fake(root / "roles/vm_pool/files", "porelo-vm", f'echo "porelo-vm $*" >> {log}\n')
    fake(bin_dir, "ssh", f'echo "ssh $*" >> {log}\n')
    fake(bin_dir, "curl", f'echo "curl $*" >> {log}\nexit 22\n')

    def call(*arguments):
        environment = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "HOME": str(tmp_path)}
        done = subprocess.run([str(script), *arguments], capture_output=True, text=True, env=environment, check=False)
        return done, log.read_text() if log.exists() else ""

    return root / "target/rehearsal", call


def test_a_start_over_an_earlier_rehearsals_vm_is_refused_and_names_it(tmp_path):
    """Prevent a rehearsal taking over, or later deleting, a VM another run left."""
    state, call = rehearsal(tmp_path, listed="porelo-host-rehearsal-20261106t120000z\n")
    done, calls = call("start")
    assert done.returncode != 0, "a start over a left VM must fail"
    assert "porelo-host-rehearsal-20261106t120000z" in done.stderr, "the refusal names what was left"
    assert "porelo-vm" not in calls and "curl" not in calls, "nothing is fetched or made after the refusal"
    assert not state.exists(), "no run's directory is made"


def test_down_deletes_only_the_vm_its_own_run_made(tmp_path):
    """Prevent down deleting a VM by any name but the one its start recorded."""
    state, call = rehearsal(tmp_path)
    state.mkdir(parents=True)
    (state / "name").write_text("porelo-host-rehearsal-20261106t150000z\n")
    (state / "organization").write_text("\n")
    done, calls = call("down")
    assert done.returncode == 0, done.stderr
    deleted = [line for line in calls.splitlines() if line.startswith("porelo-vm delete")]
    assert deleted == ["porelo-vm delete porelo-host-rehearsal-20261106t150000z"], "only the run's own VM is deleted"
    assert not state.exists(), "the run's directory goes with it"


def test_down_refuses_a_recorded_name_that_is_no_rehearsals(tmp_path):
    """Prevent a changed record making down delete another VM on the machine."""
    state, call = rehearsal(tmp_path)
    state.mkdir(parents=True)
    (state / "name").write_text("ubuntu26.04\n")
    done, calls = call("down")
    assert done.returncode != 0, "a down for a name that is no rehearsal's must fail"
    assert "porelo-vm delete" not in calls and "virsh" not in calls, "nothing is asked of libvirt"


def test_the_tunnel_takes_only_the_runs_host_key_and_refuses_once_it_is_gone(tmp_path, monkeypatch):
    """Prevent the tunnel trusting the person's own known hosts for the VM's address."""
    state, call = rehearsal(tmp_path)
    state.mkdir(parents=True)
    (state / "address").write_text("192.0.2.10\n")
    known = state / "known_hosts"
    known.write_text("192.0.2.10 ssh-ed25519 AAAA\n")
    monkeypatch.setenv("ROOM_TUNNEL_ONCE", "1")
    done, calls = call("tunnel", "alice", "8448")
    assert done.returncode == 0, done.stderr
    tunnel = [line for line in calls.splitlines() if line.startswith("ssh ")]
    assert len(tunnel) == 1 and f"UserKnownHostsFile={known}" in tunnel[0], "the run's host key alone is trusted"
    assert "StrictHostKeyChecking=yes" in tunnel[0] and tunnel[0].endswith("alice@192.0.2.10")
    known.unlink()
    done, calls_after = call("tunnel", "alice", "8448")
    assert calls_after == calls, "no ssh runs once the run's host key is gone"


@pytest.mark.parametrize("size", ["24x", "0", "1+1", "a[$(id)]", "16\n32", ""])
def test_a_size_that_is_no_whole_number_is_refused_before_anything_is_made(tmp_path, size):
    """Prevent a size reaching shell arithmetic, virt-install or virsh as anything but digits."""
    state, call = rehearsal(tmp_path)
    done, calls = call("start", "--memory", size)
    assert done.returncode != 0, "a start with that size must fail"
    assert calls == "", "nothing is listed, fetched or made"
    assert not state.exists(), "no run's directory is made"


def test_down_of_a_bare_run_deletes_the_vm_without_asking_it(tmp_path):
    """Prevent down keeping a bare VM a person's window prepared, whose up took the run's way in."""
    state, call = rehearsal(tmp_path, running=True)
    state.mkdir(parents=True)
    (state / "name").write_text("porelo-host-rehearsal-20261106t150000z\n")
    (state / "address").write_text("192.168.122.9\n")
    (state / "bare").write_text("")
    done, calls = call("down")
    assert done.returncode == 0, done.stderr
    assert "ssh " not in calls, "nothing is asked of the VM itself"
    assert "porelo-vm delete porelo-host-rehearsal-20261106t150000z" in calls, "the VM is deleted"
    assert not state.exists(), "the run's directory goes with it"
