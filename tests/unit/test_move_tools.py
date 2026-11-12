"""Guard the move's read-only check and the room's tunnel against saying more than they saw."""

import base64
import json
import os
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "build/move-check.sh"
TUNNEL = ROOT / "build/room-tunnel.sh"

GOOD = {
    "host_version": "porelo-host 0.5.1~snapshot.fixture\n",
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
    # The forge holds a repository under its central name, which is not the key the task names it by.
    "repos": json.dumps([{"name": "porelo-sluice"}, {"name": "porelo-other"}]),
    "other_heads": "ref: refs/heads/main\tHEAD\n" + "c" * 40 + "\trefs/heads/porelo/t9\n",
    "pulls": json.dumps([{"head": {"ref": "porelo/t1"}, "base": {"ref": "main"}}]),
    "pulls_next": "[]",
    "git_code": "0",
    "curl_code": "0",
    "credential_code": "0",
    "repos_status": "200",
    "pulls_status": "200",
    "git_err": "",
    "other_git_code": "0",
    "pulls_curl_code": "0",
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
        fake(tmp_path, "porelo-host", f'echo "host $*" >> {log}\ncat {tmp_path}/host_version\n')
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
    *" ls-remote "*"/porelo/porelo-sluice.git "*) cat {tmp_path}/heads; cat {tmp_path}/git_err >&2
        exit "$(cat {tmp_path}/git_code)" ;;
    *" ls-remote "*) cat {tmp_path}/other_heads; exit "$(cat {tmp_path}/other_git_code)" ;;
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
failed=$(cat {tmp_path}/curl_code)
case "$*" in *"/pulls?"*) [ "$failed" != 0 ] || failed=$(cat {tmp_path}/pulls_curl_code) ;; esac
status=200
case "$*" in
    *"/api/v1/orgs/porelo/repos?"*)
        status=$(cat {tmp_path}/repos_status)
        case "$*" in
            *"page=1"*) body=$(cat {tmp_path}/repos) ;;
            *) body='[]' ;;
        esac ;;
    *"/api/v1/repos/porelo/porelo-sluice/pulls?state=open"*)
        status=$(cat {tmp_path}/pulls_status)
        if [ -f {tmp_path}/pulls_endless ]; then body=$(cat {tmp_path}/pulls)
        else
            case "$*" in
                *"page=2"*) body=$(cat {tmp_path}/pulls_next) ;;
                *"page=3"*) body='[]' ;;
                *) body=$(cat {tmp_path}/pulls) ;;
            esac
        fi ;;
    *) echo "unexpected: $*" >&2; exit 99 ;;
esac
[ "$status" = 200 ] || body='{{"message":"refused by the stand-in"}}'
# As curl does: -w appends the status after the body; -f fails on one of 400 and above instead.
# A transfer that fails may still have written a whole body and its status: only the exit code says so.
case "$*" in
    *"%{{http_code}}"*) printf '%s\n%s' "$body" "$status" ;;
    *) [ "$status" -lt 400 ] || exit 22; printf '%s' "$body" ;;
esac
exit "$failed"
""",
        )
        return log

    return install


def check(tmp_path, *arguments):
    environment = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "PORELO_HOST_FORGE_CONF": str(tmp_path / "forge.conf"),
        "PORELO_HOST_PACKAGE_VERSION": GOOD["host_version"].removeprefix("porelo-host ").strip(),
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
    assert done.stdout.count("ok:") == 7 and "FAILED" not in done.stdout
    assert all(
        line.split()[0] in ("host", "task", "build", "talk", "git", "vault", "curl")
        for line in calls.read_text().splitlines()
    )
    assert "--logs=none" in calls.read_text() and "--branch=porelo/t1" in calls.read_text()


def test_the_move_refuses_a_different_host_program_build(tmp_path, porelo):
    """Prevent accepting a move whose privileged executable is not the pinned local build."""
    porelo(host_version="porelo-host stale\n")
    done = check(tmp_path, "t1", "Agent Sluice", "--wake-answered")
    assert done.returncode != 0 and "FAILED: the host program" in done.stdout


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


def test_a_reader_without_builds_fails_the_build_line_on_a_host_with_a_forge(tmp_path, porelo):
    """Prevent a move passing whose Builds nobody reads, as the host names builds: for every project on its forge."""
    calls = porelo(
        status_text="task       t1\nforge      porelo/t1\n",
        build=NO_BUILDS,
        build_code="78",
    )
    done = check(tmp_path, "t1", "Agent Sluice", "--wake-answered")
    assert done.returncode == 1, done.stdout + done.stderr
    lines = done.stdout.splitlines()
    assert len(lines) == 7 and done.stdout.count("FAILED") == 1, done.stdout
    assert any(line.startswith("FAILED") and "Build" in line and "not configured" in line for line in lines), lines
    assert any(line.startswith("ok:") and "a" * 40 in line and "last push" in line for line in lines)
    assert any(line.startswith("ok:") and "pull request" in line for line in lines)
    assert "curl " in calls.read_text(), "the PR is read from the forge"


def test_the_push_is_read_in_the_forge_repository_that_holds_the_tasks_branch(tmp_path, porelo):
    """Prevent the check asking the forge for the project.yml key, under which the forge holds no repository."""
    calls = porelo()
    done = check(tmp_path, "t1", "Agent Sluice", "--wake-answered")
    assert done.returncode == 0, done.stdout + done.stderr
    assert any(line.startswith("ok:") and "porelo/porelo-sluice" in line for line in done.stdout.splitlines())
    asked = calls.read_text()
    assert "/porelo/sluice.git" not in asked and "/repos/porelo/sluice/" not in asked, asked
    assert "/api/v1/repos/porelo/porelo-sluice/pulls" in asked
    assert "-r sluice" in asked, "the build reader still takes the task's own key"


def test_a_branch_held_by_two_repositories_names_both_and_fails(tmp_path, porelo):
    """Prevent the check picking one of two repositories for a push it cannot place."""
    porelo(other_heads=GOOD["heads"])
    done = check(tmp_path, "t1", "Agent Sluice", "--wake-answered")
    assert done.returncode == 1
    failed = [line for line in done.stdout.splitlines() if line.startswith("FAILED") and "last push" in line]
    assert failed and "porelo-sluice" in failed[0] and "porelo-other" in failed[0], done.stdout


@pytest.mark.parametrize(
    "repos", ["not JSON", "{}", "[{}]", json.dumps([{"name": "../x"}]), json.dumps([{"name": "a b"}])]
)
def test_an_invalid_repository_list_is_asked_of_no_repository(tmp_path, porelo, repos):
    """Prevent a name the forge answered reaching Git as an address it did not hold to its form."""
    calls = porelo(repos=repos)
    done = check(tmp_path, "t1", "Agent Sluice", "--wake-answered")
    assert done.returncode == 1
    assert any(line.startswith("FAILED") and "cannot say" in line for line in done.stdout.splitlines()), done.stdout
    assert "ls-remote" not in calls.read_text()


@pytest.mark.parametrize(
    "answers, named, said",
    [
        (dict(repos_status="401"), "last push", "HTTP 401 for orgs/porelo/repos"),
        (dict(repos_status="403"), "last push", "HTTP 403 for orgs/porelo/repos"),
        (dict(pulls_status="404"), "pull request", "HTTP 404 for repos/porelo/porelo-sluice/pulls"),
        (dict(credential_code="1"), "last push", "the vault gave no token for forge.example.person"),
        (
            dict(
                git_code="128",
                git_err="fatal: Authentication failed for 'http://127.0.0.1:3022/porelo/porelo-sluice.git/'\n",
            ),
            "last push",
            "fatal: Authentication failed",
        ),
    ],
)
def test_a_failing_line_says_what_was_answered(tmp_path, porelo, answers, named, said):
    """Prevent a refused token, a missing scope and a missing repository reading alike, so a move's fault is found."""
    porelo(**answers)
    done = check(tmp_path, "t1", "Agent Sluice", "--wake-answered")
    assert done.returncode == 1
    failed = [line for line in done.stdout.splitlines() if line.startswith("FAILED") and named in line]
    assert failed and said in failed[0], done.stdout
    assert "synthetic-person-token" not in done.stdout + done.stderr


def test_a_failed_pull_request_reader_fails_its_line_by_name(tmp_path, porelo):
    """Prevent a pull request counted, or a failure named vaguely, when only the forge's pull request answer fails."""
    porelo(pulls_curl_code="18")
    done = check(tmp_path, "t1", "Agent Sluice", "--wake-answered")
    assert done.returncode == 1
    failed = [line for line in done.stdout.splitlines() if line.startswith("FAILED") and "pull request" in line]
    assert failed and "gave no answer for repos/porelo/porelo-sluice/pulls" in failed[0], done.stdout


def test_a_repository_git_cannot_read_after_one_that_held_the_push_fails_the_push(tmp_path, porelo):
    """Prevent a push counted while a later repository of the project, which might hold it too, went unread."""
    porelo(other_git_code="128")
    done = check(tmp_path, "t1", "Agent Sluice", "--wake-answered")
    assert done.returncode == 1
    failed = [line for line in done.stdout.splitlines() if line.startswith("FAILED") and "last push" in line]
    assert failed and "porelo/porelo-other" in failed[0], done.stdout


def test_a_head_naming_the_tasks_branch_is_not_taken_for_its_commit(tmp_path, porelo):
    """Prevent the symref line of HEAD standing in for the pushed commit."""
    porelo(heads="ref: refs/heads/porelo/t1\tHEAD\n" + "a" * 40 + "\trefs/heads/porelo/t1\n")
    done = check(tmp_path, "t1", "Agent Sluice", "--wake-answered")
    pushed = [line for line in done.stdout.splitlines() if "last push" in line]
    assert pushed and pushed[0].startswith("ok:") and "a" * 40 in pushed[0] and "ref:" not in pushed[0], done.stdout


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
    assert any("http://127.0.0.1:3022/porelo/porelo-sluice.git" in line for line in git), git
    for line in git:
        assert "@" not in line and "--symref" in line and "--heads" not in line, "Git also advertises the default"
        assert "credential.http://127.0.0.1:3022.helper=!porelo vault credential --entry forge.example.person" in line
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
    fake(root / "build", "porelo-vm", f'echo "porelo-vm $*" >> {log}\n')
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


RENTED_COMMANDS = r"""
import argparse
import datetime
import fnmatch
import json
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import sys
import time

base = Path(os.environ['REHEARSAL_TEST_BASE'])
guest = Path(os.environ['REHEARSAL_TEST_GUEST'])
settings = json.loads((base / 'answers.json').read_text())
name = Path(sys.argv[0]).name
args = sys.argv[1:]

def event(tool, **values):
    with open(base / 'events', 'a') as stream:
        stream.write(json.dumps(dict(tool=tool, **values)) + '\n')

def mapped(value):
    pattern = r'(?<![\w/.-])/(?:root|etc|run/porelo-rehearsal|proc/cpuinfo|dev/kvm|tmp/porelo-host\.tar\.gz)(?=/|[^\w.-]|$)'
    return re.sub(pattern, lambda match: str(guest) + match[0], value)

def alive(pid):
    try:
        return Path(f'/proc/{pid}/stat').read_text().rsplit(') ', 1)[1][0] != 'Z'
    except FileNotFoundError:
        return False

if name == 'ssh':
    remote = shlex.split(args[args.index('--') + 2])
    body = sys.stdin.read()
    event('ssh', args=args, remote=remote)
    known = next((value.split('=', 1)[1] for value in args if value.startswith('UserKnownHostsFile=')), None)
    if 'StrictHostKeyChecking=accept-new' in args and known and not Path(known).read_text():
        Path(known).write_text('192.0.2.10 ssh-ed25519 AAAAHOST\n')
    if (base / 'connection-lost').exists():
        sys.exit(255)
    if remote[:3] == ['exec', 'env', '-i']:
        remote = remote[4:]
    if remote[:2] == ['sudo', '-n']:
        if settings.get('sudo_denied'):
            sys.exit(1)
        remote = remote[2:]
    cleanup = len(remote) >= 4 and remote[:2] == ['bash', '-s'] and remote[2].startswith('porelo-rehearsal-')
    if cleanup and settings.get('cleanup_rc'):
        (base / 'connection-lost').touch()
        sys.exit(settings['cleanup_rc'])
    if cleanup and settings.get('cleanup_sleep'):
        event('cleanup_signal', disposition=int(signal.getsignal(signal.SIGTERM)))
        (base / 'cleanup-sleeping').touch()
        time.sleep(1)
    if remote[:2] == ['python3', '-I'] and len(remote) > 2 and remote[2].endswith('/porelo-host-check'):
        if settings.get('check_transport_error'):
            print('preflight connection failed', file=sys.stderr)
            sys.exit(255)
        parser = argparse.ArgumentParser()
        parser.add_argument('--limits')
        parser.add_argument('--choices', default='{}')
        parser.add_argument('--wait-packages', type=int, default=0)
        values = parser.parse_args(remote[3:])
        event('check', limits=json.loads(values.limits) if values.limits else None,
              choices=json.loads(values.choices), wait=values.wait_packages)
        answer = dict(v=1, ok=not settings.get('check_failure'), complete=True,
                      findings=[dict(id='ports', state='fail' if settings.get('check_failure') else 'pass', found=[3001])])
        print(json.dumps(answer))
        sys.exit(1 if settings.get('check_failure') else 0)
    result = subprocess.run([mapped(value) for value in remote], input=mapped(body), text=True, capture_output=True)
    output = result.stdout
    if output.startswith('claimed ') and settings.get('claim_pause'):
        if settings.get('claim_reply_first'):
            sys.stdout.write(output)
            sys.stdout.flush()
            output = ''
        (base / 'claim-sleeping').touch()
        time.sleep(0.5)
    staging = guest / 'run/porelo-rehearsal'
    if settings.get('steal_before_write') == 'machine' and (staging / 'porelo-host.tar.gz').exists() and not (base / 'owner-stolen').exists():
        (staging / 'owner').write_text('another-run\n')
        target = guest / 'etc/porelo-host/setup/machine.yml'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('foreign machine\n')
        (base / 'owner-stolen').touch()
    if settings.get('bad_claim_reply') and output.startswith('claimed '):
        output = 'claimed another-token\n'
    sys.stdout.write(output)
    sys.stderr.write(result.stderr)
    sys.exit(result.returncode if result.returncode >= 0 else 128 - result.returncode)
elif name == 'ssh-keygen':
    if '-y' in args:
        print(settings.get('public_key', 'ssh-ed25519 AAAATEST'))
    else:
        key = Path(args[args.index('-f') + 1])
        key.write_text('stand-in key')
        Path(str(key) + '.pub').write_text('ssh-ed25519 AAAAHOST\n')
elif name == 'python3':
    if len(args) > 1 and args[-2] == 'down.lines' and settings.get('emit_failure'):
        sys.exit(73)
    os.execv(sys.executable, [sys.executable, *args])
elif name == 'date':
    forms = {'+%s': '2000000000', '+%Y%m%dt%H%M%Sz': '20330518t033320z',
             '+%Y-%m-%dT%H:%M:%SZ': '2033-05-18T03:33:20Z'}
    if len(args) == 2 and args[0] == '-u' and args[1] in forms:
        print(forms[args[1]])
    else:
        os.execv('/usr/bin/date', ['date', *args])
elif name == 'collection-build':
    event(name)
    target = Path(os.environ['REHEARSAL_TEST_CHECKOUT']) / 'target/rented/porelo-host-test.tar.gz'
    target.write_text('stand-in collection')
elif name == 'mkdir':
    staging = guest / 'run/porelo-rehearsal'
    if str(staging) in args and settings.get('claim_race') and not staging.exists():
        staging.mkdir(mode=0o700)
        (staging / 'owner').write_text('another-run\n')
    os.execv('/usr/bin/mkdir', ['mkdir', *args])
elif name == 'install':
    filtered = []
    position = 0
    while position < len(args):
        if args[position] in ('-o', '-g'):
            position += 2
        else:
            filtered.append(args[position])
            position += 1
    os.execv('/usr/bin/install', ['install', *filtered])
elif name == 'rm':
    result = subprocess.run(['/usr/bin/rm', *args], check=False)
    if settings.get('steal_before_write') == 'collection' and str(guest / 'root/porelo-host-inventory.yml') in args and not (base / 'owner-stolen').exists():
        staging = guest / 'run/porelo-rehearsal'
        (staging / 'owner').write_text('another-run\n')
        (staging / 'porelo-host.tar.gz').write_text('foreign collection\n')
        (base / 'owner-stolen').touch()
    sys.exit(result.returncode)
elif name == 'cat':
    destination = os.readlink('/proc/self/fd/1')
    if settings.get('check_upload_failure') and destination == str(guest / 'run/porelo-rehearsal/porelo-host-check'):
        print('preflight upload refused', file=sys.stderr)
        sys.exit(73)
    if settings.get('inventory_pause') and destination in (str(guest / 'root/porelo-host-inventory.yml'), str(guest / 'root/porelo-host-inventory.yml.tmp')):
        contents = sys.stdin.read()
        split = len(contents) // 2
        sys.stdout.write(contents[:split])
        sys.stdout.flush()
        (base / 'inventory-sleeping').touch()
        time.sleep(30)
        sys.stdout.write(contents[split:])
    else:
        os.execv('/usr/bin/cat', ['cat', *args])
elif name == 'apt-get':
    event(name, args=args)
    if 'install' in args:
        (guest / 'packages').touch()
        if settings.get('before_inventory'):
            if settings.get('partial_inventory'):
                (guest / 'root/porelo-host-inventory.yml').write_text('partial inventory\n')
            sys.exit(2)
        if settings.get('sleep_before_inventory'):
            (base / 'sleeping').touch()
            time.sleep(30)
elif name == 'ansible-galaxy':
    event(name, args=args)
elif name == 'systemd-run':
    unit = next(value.split('=', 1)[1] for value in args if value.startswith('--unit='))
    command = args[args.index('bash'):]
    request = json.dumps(dict(unit=unit, command=command, body=sys.stdin.read())) + '\n'
    queue = base / 'queue'
    (queue / (unit + '.tmp')).write_text(request)
    (queue / (unit + '.tmp')).replace(queue / (unit + '.request'))
    response = queue / (unit + '.response')
    while not response.exists():
        time.sleep(0.01)
    answer = json.loads(response.read_text())
    # systemd collects the unit (--collect), so a later run may take the same name.
    response.unlink()
    sys.stdout.write(answer['stdout'])
    sys.stderr.write(answer['stderr'])
    sys.exit(answer['code'])
elif name == 'systemctl':
    units = base / 'units'
    if args[0] == 'list-units':
        for path in units.iterdir():
            retained = settings.get('retained_unit_state') and not (base / 'unit-reset').exists()
            if fnmatch.fnmatch(path.name + '.service', args[-1]) and (alive(int(path.read_text())) or retained):
                print(path.name + '.service loaded ' + (settings.get('retained_unit_state') or 'active') + ' waiting')
    elif args[0] == 'stop':
        event(name, args=args)
        path = units / args[1].removesuffix('.service')
        if not path.exists():
            sys.exit(5)
        pid = int(path.read_text())
        if alive(pid):
            os.killpg(pid, signal.SIGTERM)
            deadline = time.monotonic() + 1
            while alive(pid) and time.monotonic() < deadline:
                time.sleep(0.01)
            if alive(pid):
                os.killpg(pid, signal.SIGKILL)
    elif args[0] == 'show':
        print(settings.get('retained_unit_state') or 'inactive')
    elif args[0] == 'reset-failed':
        event(name, args=args)
        if not (units / args[1].removesuffix('.service')).exists():
            sys.exit(5)
        (base / 'unit-reset').touch()
    else:
        event(name, args=args)
elif name == 'ansible-playbook':
    verb = args[-1].rsplit('.', 1)[-1]
    event(name, verb=verb, term_disposition=int(signal.getsignal(signal.SIGTERM)))
    host = guest / 'etc/porelo-host'
    if verb == 'up':
        host.mkdir(parents=True, exist_ok=True)
        (host / 'forge.conf').write_text('host=rented\nname=rented.localhost\naccount=rehearsal\n')
        (host / 'firewall.nft').write_text('retained firewall\n')
        # Up owns root's keys: the base role seeds them, and a follow later writes the host admins' keys there.
        root_keys = guest / 'etc/ssh/authorized_keys/root'
        root_keys.parent.mkdir(parents=True, exist_ok=True)
        if settings.get('no_root_keys'):
            root_keys.unlink(missing_ok=True)
        else:
            root_keys.write_text(settings.get('root_keys', 'ssh-ed25519 AAAATEST\n'))
        policy = guest / 'etc/ssh/sshd_config.d/10-porelo-host.conf'
        policy.write_text('role-owned SSH policy\n')
        if settings.get('steal_owner'):
            (guest / 'run/porelo-rehearsal/owner').write_text('another-run\n')
        if settings.get('up_sleep'):
            (base / 'sleeping').touch()
            time.sleep(30)
        print(json.dumps(dict(state='failed' if settings.get('up_bad_lines') else 'host')))
        sys.exit(settings.get('up_rc', 0))
    if settings.get('down_sleep'):
        (base / 'down-sleeping').touch()
        time.sleep(1)
    partial = 'partial' in (guest / 'root/porelo-host-inventory.yml').read_text()
    print(json.dumps(dict(state=settings.get('down_state', 'failed' if partial else 'ok'), task='host down')))
    sys.exit(settings.get('down_rc', 2 if partial else 0))
elif name == 'sshd':
    event(name, args=args)
elif name == 'org-program':
    event('org', args=args)
    verb = args[2] if len(args) > 2 else ''
    root_keys = guest / 'etc/ssh/authorized_keys/root'
    taken = [' '.join(line.split()[:2]) for line in (root_keys.read_text().splitlines() if root_keys.exists() else [])]
    if verb == 'refresh' and settings.get('org_key', 'ssh-ed25519 AAAAORG') not in taken:
        print('rented: root@192.0.2.10: Permission denied (publickey).', file=sys.stderr)
        sys.exit(69)
    if settings.get('org_rc', {}).get(verb):
        sys.exit(settings['org_rc'][verb])
elif name == 'central-token':
    if settings.get('central_token_rc'):
        sys.exit(settings['central_token_rc'])
    print(settings.get('central_token', 'synthetic-central-token'))
elif name == 'porelo-host':
    event(name, args=args)
    if args[:3] == ['org', 'status', '--json']:
        calls = base / 'status-calls'
        count = int(calls.read_text()) + 1 if calls.exists() else 1
        calls.write_text(str(count))
        admitted = count >= settings.get('admitted_after', 1)
        login = settings.get('person', 'test-person')
        persons = [dict(login=login, state='active', host_admin=True,
                        projects=[dict(project='foo-project', role='admin')])] if admitted else []
        print(json.dumps(dict(host='rented', refused=None, commit='a' * 40, pinned=None, persons=persons)))
elif name == 'porelo':
    given = sys.stdin.read()
    for line in given.splitlines():
        if line.startswith('vault-new '):
            (base / 'given-passphrase').write_text(line.split(' ', 1)[1])
    if args[:2] == ['vault', 'put']:
        if 'porelo-rehearsal-refused-token' in given:
            (base / 'refused-token').touch()
        else:
            (base / 'refused-token').unlink(missing_ok=True)
    secret = settings.get('central_token', 'synthetic-central-token')
    event(name, args=args, stdin_lines=[line.split(' ', 1)[0] if ' ' in line else '<value>' for line in given.splitlines()],
          stdin_has_token=secret in given)
    if args[:2] == ['host', 'central-state']:
        print(json.dumps(dict(project=args[-1], state='even')))
    if args[:2] == ['host', 'push'] and 'no-such-repository' in args:
        sys.exit(64)
    if args[:2] == ['host', 'push'] and (base / 'refused-token').exists():
        print(args[-1] + ': central forge github.com refused authentication (HTTP 401)')
        sys.exit(1)
    sys.exit(settings.get('porelo_rc', {}).get(args[1] if len(args) > 1 else '', 0))
else:
    raise SystemExit('unexpected stand-in ' + name)
"""


class RentedServer:
    """Execute SSH commands on a private filesystem; external jobs belong to the test, not the SSH client."""

    def __init__(self, tmp_path, settings):
        import threading

        self.base = tmp_path
        self.guest = tmp_path / "guest"
        self.root = tmp_path / "checkout"
        self.bin = tmp_path / "bin"
        self.settings = settings
        self.jobs = []
        self.queue = tmp_path / "queue"
        self.queue.mkdir()
        self.stopped = threading.Event()
        self.handlers = []
        self.root.joinpath("build").mkdir(parents=True)
        self.script = self.root / "build/rehearse-move.sh"
        self.script.write_bytes(REHEARSE.read_bytes())
        self.script.chmod(0o755)
        check = self.root / "roles/check/files"
        check.mkdir(parents=True)
        for name in ("porelo-host-check", "limits.json"):
            (check / name).write_bytes((ROOT / "roles/check/files" / name).read_bytes())
        for path in ("root/.ssh", "etc/ssh/sshd_config.d", "run", "proc", "dev", "tmp"):
            (self.guest / path).mkdir(parents=True, exist_ok=True)
        (self.guest / "etc/ssh/ssh_host_ed25519_key.pub").write_text("ssh-ed25519 AAAAHOST\n")
        (self.guest / "proc/cpuinfo").write_text("flags : vmx\n" if settings.get("cpu", True) else "flags :\n")
        if settings.get("device", True):
            (self.guest / "dev/kvm").touch()
        (tmp_path / "units").mkdir()
        self.bin.mkdir()
        for name in (
            "ssh",
            "ssh-keygen",
            "date",
            "collection-build",
            "mkdir",
            "install",
            "apt-get",
            "ansible-galaxy",
            "systemd-run",
            "systemctl",
            "ansible-playbook",
            "sshd",
            "org-program",
            "central-token",
            "porelo",
            "porelo-host",
        ):
            path = self.bin / name
            path.write_text(f"#!{sys.executable}\n" + RENTED_COMMANDS)
            path.chmod(0o755)
        if settings.get("emit_failure"):
            reader = self.bin / "python3"
            reader.write_text(f"#!{sys.executable}\n" + RENTED_COMMANDS)
            reader.chmod(0o755)
        optional = []
        if settings.get("steal_before_write") == "collection":
            optional.append("rm")
        if settings.get("inventory_pause") or settings.get("check_upload_failure"):
            optional.append("cat")
        for name in optional:
            command = self.bin / name
            command.write_text(f"#!{sys.executable}\n" + RENTED_COMMANDS)
            command.chmod(0o755)
        fake(self.root / "build", "tools.sh", 'exec "$REHEARSAL_TEST_BIN/collection-build" "$@"\n')
        for name in ("virsh", "curl", "podman", "scp"):
            fake(self.bin, name, f'echo "unexpected {name}" >&2\nexit 99\n')
        self.key = tmp_path / "private key"
        self.key.write_text("stand-in private key\n")
        self.state = self.root / "target/rented"
        self.environment = {
            **os.environ,
            "HOME": str(tmp_path),
            "PATH": f"{self.bin}:{os.environ['PATH']}",
            "PYTHONDONTWRITEBYTECODE": "1",
            "REHEARSAL_TEST_BASE": str(tmp_path),
            "REHEARSAL_TEST_GUEST": str(self.guest),
            "REHEARSAL_TEST_CHECKOUT": str(self.root),
            "REHEARSAL_TEST_BIN": str(self.bin),
            "PORELO_REHEARSAL_READ_KEYS_PROGRAM": "true",
        }
        self.environment.pop("PORELO_REHEARSAL_HARD_STOP_SECONDS", None)
        (tmp_path / "answers.json").write_text(json.dumps(settings))

        def answer_job(process, request, destination):
            stdout, stderr = process.communicate(request["body"])
            answer = dict(
                code=process.returncode if process.returncode >= 0 else 128 - process.returncode,
                stdout=stdout,
                stderr=stderr,
            )
            temporary = destination.with_suffix(".tmp")
            temporary.write_text(json.dumps(answer))
            temporary.replace(destination)

        def serve():
            while not self.stopped.wait(0.01):
                for path in self.queue.glob("*.request"):
                    request = json.loads(path.read_text())
                    path.unlink()
                    process = subprocess.Popen(
                        request["command"],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        env=self.environment,
                        start_new_session=True,
                    )
                    self.jobs.append(process)
                    (tmp_path / "units" / request["unit"]).write_text(str(process.pid))
                    handler = threading.Thread(
                        target=answer_job,
                        args=(process, request, self.queue / (request["unit"] + ".response")),
                        daemon=True,
                    )
                    self.handlers.append(handler)
                    handler.start()

        self.thread = threading.Thread(target=serve, daemon=True)
        self.thread.start()

    def events(self, tool):
        path = self.base / "events"
        return (
            [
                row
                for row in map(json.loads, path.read_text().splitlines())
                if row["tool"] == tool and row.get("args") != ["--version"]
            ]
            if path.exists()
            else []
        )

    def down_calls(self):
        return [row for row in self.events("ansible-playbook") if row["verb"] == "down"]

    def report(self):
        reports = list((self.base / ".porelo/rehearsal").glob("192.0.2.10-*"))
        assert len(reports) == 1
        return reports[0], (reports[0] / "steps").read_text().splitlines()

    def call(
        self,
        *arguments,
        hard_stop=None,
        signal_at=None,
        signal_on_ok=None,
        signal_before_wait=None,
        signal_number=signal.SIGTERM,
        address="192.0.2.10",
        timeout=10,
    ):
        environment = dict(self.environment)
        if hard_stop is not None:
            environment["PORELO_REHEARSAL_HARD_STOP_SECONDS"] = str(hard_stop)
        command = [str(self.script), "rented", address, "--key", str(self.key), *arguments]
        if signal_on_ok:
            wrapper = """printf() {
    command printf "$@"
    case "$*" in *"OK $REHEARSAL_SIGNAL_STEP "*)
        if [ "${signal_sent:-}" != yes ]; then signal_sent=yes; kill -TERM "$$"; fi ;;
    esac
}
. "$0"
"""
            environment["REHEARSAL_SIGNAL_STEP"] = signal_on_ok
            command = ["sh", "-c", wrapper, *command]
        if signal_before_wait:
            wrapper = """wait() {
    if [ "${current:-}" = "$REHEARSAL_SIGNAL_WAIT" ] && [ "${signal_sent:-}" != yes ]; then
        while [ ! -e "$REHEARSAL_TEST_BASE/sleeping" ]; do sleep 0.01; done
        signal_sent=yes
        kill -TERM "$$"
    fi
    command wait "$@"
}
. "$0"
"""
            environment["REHEARSAL_SIGNAL_WAIT"] = signal_before_wait
            command = ["sh", "-c", wrapper, *command]
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=environment,
            start_new_session=True,
        )
        try:
            if signal_at:
                deadline = time.monotonic() + 7
                while not (self.base / signal_at).exists() and process.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.01)
                if (self.base / signal_at).exists():
                    process.send_signal(signal_number)
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            pytest.fail("the rehearsal failed to stop and report within its stand-in deadline")
        return subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)

    def close(self):
        self.stopped.set()
        self.thread.join()
        for process in self.jobs:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        for handler in self.handlers:
            handler.join()


@pytest.fixture
def rented(tmp_path):
    """All commands are local stand-ins; every launched remote worker is reclaimed."""
    servers = []

    def make(**settings):
        server = RentedServer(tmp_path, settings)
        servers.append(server)
        return server

    yield make
    for server in servers:
        server.close()


def test_rented_atomic_claim_refuses_an_existing_host_without_any_other_command(rented):
    """Prevent taking over or inspecting a host that this run did not claim."""
    server = rented()
    host = server.guest / "etc/porelo-host"
    host.mkdir()
    (host / "keep").write_text("untouched")
    done = server.call()
    assert done.returncode != 0
    assert len(server.events("ssh")) == 1 and not server.down_calls()
    assert (host / "keep").read_text() == "untouched"
    assert not (server.state / "owns-host").exists()


@pytest.mark.parametrize("race", [False, True])
def test_rented_atomic_claim_never_steals_another_runs_staging(rented, race):
    """Prevent concurrent setup or cleanup from using another run's staging and owner token."""
    server = rented(claim_race=race)
    staging = server.guest / "run/porelo-rehearsal"
    if not race:
        staging.mkdir()
        (staging / "owner").write_text("another-run\n")
    done = server.call()
    assert done.returncode != 0
    assert len(server.events("ssh")) == 1
    assert not server.events("check") and not server.down_calls()
    assert (staging / "owner").read_text() == "another-run\n"
    assert not (server.state / "owns-host").exists()


@pytest.mark.parametrize("settings", [{"bad_claim_reply": True}, {"sudo_denied": True}])
def test_rented_requires_the_exact_claim_answer_before_cleanup_can_read_anything(rented, settings):
    """Prevent an absent, foreign, or unconfirmed owner token authorizing cleanup reads."""
    server = rented(**settings)
    done = server.call("--login", "rehearsal")
    assert done.returncode != 0 and len(server.events("ssh")) == 1
    assert not (server.state / "owns-host").exists()


@pytest.mark.parametrize("public_key", ["ssh-rsa AAAATEST", "ecdsa-sha2-nistp256 AAAATEST", "garbage"])
def test_rented_ed25519_only_keys_are_checked_before_any_ssh(rented, public_key):
    """Prevent an unusable admin key replacing server login keys before up can reject it."""
    server = rented(public_key=public_key)
    done = server.call()
    assert done.returncode != 0 and not server.events("ssh")


@pytest.mark.parametrize("login", ["root", "rehearsal"])
def test_rented_key_pinning_replaces_symlinks_and_preserves_their_targets(rented, login):
    """Prevent replacing the run's login key from overwriting a symlink's unrelated target."""
    server = rented()
    protected = server.guest / "protected"
    protected.write_text("unrelated data\n")
    root_key = server.guest / "root/.ssh/authorized_keys"
    login_key = server.guest / f"etc/ssh/authorized_keys/{login}"
    login_key.parent.mkdir()
    root_key.symlink_to(protected)
    login_key.symlink_to(protected)
    done = server.call("--login", login)
    assert done.returncode == 0, done.stderr
    assert protected.read_text() == "unrelated data\n"
    for path, mode in ((root_key, 0o600), (login_key, 0o644)):
        assert not path.is_symlink() and path.read_text() == "ssh-ed25519 AAAATEST\n"
        assert path.stat().st_mode & 0o777 == mode


def test_rented_down_really_runs_once_and_retains_the_hosts_firewall_and_ssh_policy(rented):
    """Prevent a successful rehearsal deleting the retained firewall or changing the host's SSH policy."""
    server = rented()
    done = server.call()
    assert done.returncode == 0, done.stderr
    assert len(server.down_calls()) == 1
    assert (server.guest / "etc/porelo-host/firewall.nft").read_text() == "retained firewall\n"
    assert (server.guest / "etc/ssh/sshd_config.d/10-porelo-host.conf").read_text() == "role-owned SSH policy\n"
    assert not server.events("sshd")
    assert not (server.guest / "run/porelo-rehearsal").exists()
    report, steps = server.report()
    assert [line.split()[:2] for line in steps[:-1]] == [
        ["OK", "refuse-existing"],
        ["OK", "check"],
        ["OK", "up"],
        ["SKIP", "stop"],
        ["SKIP", "project"],
        ["SKIP", "judge"],
        ["SKIP", "push-pull"],
        ["OK", "down"],
        ["SKIP", "read-keys"],
    ]
    assert json.loads((report / "down.lines").read_text())["state"] == "ok"
    assert report.stat().st_mode & 0o777 == 0o700
    report.rename(server.base / "first-report")
    calls_before = len(server.events("ssh"))
    assert (server.guest / "root/porelo-rehearsal-down").exists()
    again = server.call()
    assert "OK refuse-existing" in again.stderr, again.stderr
    assert len(server.events("ssh")) > calls_before + 1
    assert (server.guest / "etc/porelo-host/firewall.nft").read_text() == "retained firewall\n"


def test_rented_down_owner_token_protects_another_runs_host(rented):
    """Prevent cleanup taking down a host after its staging ownership has changed."""
    server = rented(steal_owner=True)
    done = server.call()
    assert done.returncode != 0 and not server.down_calls()
    assert (server.guest / "run/porelo-rehearsal/owner").read_text() == "another-run\n"
    assert (server.guest / "etc/porelo-host/firewall.nft").exists()


@pytest.mark.parametrize("settings", [{"check_failure": True}, {"before_inventory": True}])
def test_rented_down_ran_condition_does_not_claim_removal_without_an_inventory(rented, settings):
    """Prevent a failed bootstrap being reported as a host whose down actually ran."""
    server = rented(**settings)
    done = server.call()
    assert done.returncode != 0 and not server.down_calls()
    report, steps = server.report()
    reason = "check failed before up" if settings.get("check_failure") else "up did not reach its inventory"
    assert any(line.startswith("SKIP down ") and reason in line for line in steps)
    assert not any(line.startswith("OK down ") for line in steps)
    assert not (report / "down.lines").exists()
    assert not (server.guest / "run/porelo-rehearsal").exists()


def test_rented_down_attempts_a_partial_inventory_and_reports_the_actual_failure(rented):
    """Prevent partial inventory files from silently bypassing the host's real removal checks."""
    server = rented(before_inventory=True, partial_inventory=True)
    done = server.call()
    assert done.returncode != 0 and len(server.down_calls()) == 1
    report, steps = server.report()
    assert any(line.startswith("FAIL down ") and "exit 2" in line for line in steps)
    assert json.loads((report / "down.lines").read_text())["state"] == "failed"


@pytest.mark.parametrize("code", [2, 124, 255])
def test_rented_down_exit_status_and_saved_up_lines_survive_cleanup_failures(rented, code):
    """Prevent losing completed up evidence, hiding down's real status, or retrying a dead connection."""
    server = rented(**({"cleanup_rc": code} if code in (124, 255) else {"down_rc": code}))
    done = server.call()
    assert done.returncode != 0
    report, steps = server.report()
    assert json.loads((report / "up.lines").read_text())["state"] == "host"
    assert any(line.startswith("FAIL down ") and f"exit {code}" in line for line in steps)
    assert steps[-1].startswith("LEFT on server ")
    if code in (124, 255):
        assert not server.down_calls()
        assert server.events("ssh")[-1]["remote"][:2] == ["bash", "-s"]
    else:
        assert len(server.down_calls()) == 1
        assert json.loads((report / "down.lines").read_text())["state"] == "ok"


@pytest.mark.parametrize("state", ["failed", "waiting"])
def test_rented_down_failure_lines_cannot_be_hidden_by_a_zero_exit_status(rented, state):
    """Prevent accepting an incomplete removal when its process incorrectly exits successfully."""
    server = rented(down_state=state)
    done = server.call()
    assert done.returncode != 0 and len(server.down_calls()) == 1
    report, steps = server.report()
    assert json.loads((report / "down.lines").read_text())["state"] == state
    assert any(line.startswith("FAIL down ") for line in steps)
    assert steps[-1].startswith("LEFT on server ")


@pytest.mark.parametrize("zone", [None, "zone-2"])
def test_rented_delete_instruction_identifies_the_server_and_retained_software_at_the_current_utc_time(rented, zone):
    """Prevent delaying deletion because a report falsely claims that the rented server was restored."""
    server = rented()
    done = server.call(*(() if zone is None else ("--zone", zone)))
    assert done.returncode == 0, done.stderr
    report, steps = server.report()
    place = "" if zone is None else f" in zone {zone}"
    assert (
        steps[-1]
        == done.stderr.splitlines()[-1]
        == (
            f"delete the server 192.0.2.10{place} now (2033-05-18T03:33:20Z); "
            "the host's down ran, its software stays until the server is deleted"
        )
    )
    assert (server.guest / "packages").exists() and (server.guest / "etc/porelo-host/firewall.nft").exists()


@pytest.mark.parametrize("zone", ["", "ZONE", "zone/x", "zone\nother"])
def test_rented_invalid_zones_are_refused_before_any_ssh(rented, zone):
    """Prevent an ambiguous location from reaching the server-deletion instruction."""
    server = rented()
    done = server.call("--zone", zone)
    assert done.returncode != 0 and not server.events("ssh")


@pytest.mark.parametrize("age", [19799, 19800])
def test_rented_hard_stop_default_really_bounds_the_lease_at_19800_seconds(rented, age):
    """Prevent a changed default deadline from silently extending the paid server lease."""
    from datetime import datetime, timezone

    server = rented(sleep_before_inventory=True)
    ordered = datetime.fromtimestamp(2000000000 - age, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    done = server.call("--order-time", ordered)
    assert done.returncode != 0
    if age == 19800:
        assert not server.events("ssh")
    else:
        assert server.events("ssh"), done.stderr
        assert "hard stop" in done.stderr
        report, steps = server.report()
        assert any(line.startswith("SKIP down ") for line in steps)
        assert "the host's down ran" not in steps[-1]


def test_rented_interrupt_stops_the_real_remote_unit_before_down(rented):
    """Prevent an installation owned by the remote supervisor continuing after cleanup."""
    server = rented(up_sleep=True)
    done = server.call(signal_at="sleeping")
    assert done.returncode != 0 and len(server.down_calls()) == 1
    assert all(process.poll() is not None for process in server.jobs)
    assert server.events("systemctl")[0]["args"][0] == "stop"


def test_rented_cleanup_signals_do_not_make_its_children_ignore_term_or_repeat_down(rented):
    """Prevent a signal during cleanup from disabling timeout termination or running down twice."""
    server = rented(cleanup_sleep=True)
    done = server.call(signal_at="cleanup-sleeping")
    assert done.returncode != 0 and len(server.down_calls()) == 1
    assert server.events("cleanup_signal")[0]["disposition"] == int(signal.SIG_DFL)


def test_rented_check_uses_the_roles_limits_choices_and_package_wait(rented):
    """Prevent preflight bypassing the port and package-lock checks that installation relies on."""
    server = rented(check_failure=True)
    done = server.call()
    assert done.returncode != 0
    checks = server.events("check")
    assert len(checks) == 1
    assert checks[0]["limits"] == json.loads((ROOT / "roles/check/files/limits.json").read_text())
    assert checks[0]["choices"] == {"forge": True, "kvm": False, "ports": [3001]}
    assert checks[0]["wait"] == 300
    report, steps = server.report()
    assert json.loads((report / "check.out").read_text())["findings"][0]["state"] == "fail"
    assert any(line.startswith("FAIL check ") and str(report / "check.out") in line for line in steps)


@pytest.mark.parametrize("cpu,device", [(True, True), (False, True), (True, False), (False, False)])
def test_rented_kvm_is_enabled_only_when_both_cpu_and_device_were_observed(rented, cpu, device):
    """Prevent installing a host with KVM that this machine cannot actually use."""
    server = rented(cpu=cpu, device=device)
    done = server.call("--login", "rehearsal")
    assert done.returncode == 0, done.stderr
    inventory = (server.guest / "root/porelo-host-inventory.yml").read_text()
    assert f"porelo_host_kvm: {str(cpu and device).lower()}" in inventory
    assert "porelo_host_name: rented" in inventory
    assert all(call["remote"][:2] == ["sudo", "-n"] for call in server.events("ssh"))


def test_rented_ssh_never_uses_another_identity_or_unpinned_host_key(rented):
    """Prevent cleanup reconnecting with another identity or trusting a changed server key."""
    server = rented()
    done = server.call()
    assert done.returncode == 0, done.stderr
    calls = server.events("ssh")
    assert len(calls) > 3
    for index, call in enumerate(calls):
        args = call["args"]
        for option in (
            "BatchMode=yes",
            "IdentitiesOnly=yes",
            "ConnectTimeout=5",
            "IdentityAgent=none",
            f"UserKnownHostsFile={server.state / 'known_hosts'}",
            "GlobalKnownHostsFile=/dev/null",
            f"StrictHostKeyChecking={'accept-new' if index == 0 else 'yes'}",
        ):
            assert any(args[position : position + 2] == ["-o", option] for position in range(len(args)))
        assert args[args.index("-i") + 1] == str(server.key)


@pytest.mark.parametrize("step", ["refuse-existing", "check", "up"])
def test_rented_a_signal_after_ok_cannot_also_fail_the_completed_step(rented, step):
    """Prevent a signal in step reporting from producing contradictory or unnamed results."""
    server = rented()
    done = server.call(signal_on_ok=step)
    assert done.returncode != 0
    report, steps = server.report()
    assert any(line.startswith(f"OK {step} ") for line in steps)
    assert not any(line.startswith(f"FAIL {step} ") for line in steps)
    assert any("between steps" in line and step in line for line in steps if line.startswith("FAIL "))
    assert len(server.down_calls()) == (1 if step == "up" else 0)


def test_rented_stop_tree_allows_term_cleanup_before_forcing_a_child_to_die(tmp_path):
    """Prevent immediate KILL from skipping a process's TERM cleanup and leaving child processes alive."""
    library = tmp_path / "library.sh"
    source = REHEARSE.read_text()
    library.write_text(source.split("\n[ $# -ge 1 ] || usage\n")[0])
    parent = tmp_path / "parent.sh"
    ready = tmp_path / "ready"
    cleaned = tmp_path / "cleaned"
    parent.write_text(
        f"trap 'sleep 0.1; printf cleaned > {shlex.quote(str(cleaned))}; exit 0' TERM\n"
        f"printf ready > {shlex.quote(str(ready))}\n"
        "while :; do sleep 0.1; done\n"
    )
    code = f""". {shlex.quote(str(library))}
sh {shlex.quote(str(parent))} &
worker=$!
while [ ! -f {shlex.quote(str(ready))} ]; do sleep 0.01; done
stop_tree "$worker"
wait "$worker" || true
"""
    done = subprocess.run(["sh", "-c", code], capture_output=True, text=True, timeout=8, check=False)
    assert done.returncode == 0, done.stderr
    assert cleaned.read_text() == "cleaned"


@pytest.mark.parametrize(
    "address,arguments",
    [
        ("example.org", ()),
        ("192.0.2.10\n192.0.2.11", ()),
        ("192.0.2.10 extra", ()),
        ("192.0.2.10", ("--key", "/missing/key")),
        ("192.0.2.10", ("--order-time", "2099-01-01T00:00Z")),
        ("192.0.2.10", ("--order-time", "yesterday")),
        ("192.0.2.10", ("--login", "root;id")),
    ],
)
def test_rented_unsafe_targets_keys_and_times_cannot_reach_ssh(rented, address, arguments):
    """Prevent malformed inputs or future lease times from selecting a server or shell command."""
    server = rented()
    done = server.call(*arguments, address=address)
    assert done.returncode != 0 and not server.events("ssh")


def test_rented_an_existing_local_state_cannot_be_overwritten(rented):
    """Prevent losing an earlier run's server ownership or pinned key records."""
    server = rented()
    server.state.mkdir(parents=True)
    (server.state / "keep").write_text("earlier run\n")
    done = server.call()
    assert done.returncode != 0 and not server.events("ssh")
    assert (server.state / "keep").read_text() == "earlier run\n"


@pytest.mark.parametrize("code", [124, 255])
def test_rented_remote_playbook_failures_keep_their_down_lines(rented, code):
    """Prevent a playbook exit code being mistaken for failure of the still-open SSH connection."""
    server = rented(down_rc=code)
    done = server.call()
    assert done.returncode == code and len(server.down_calls()) == 1
    report, steps = server.report()
    assert json.loads((report / "up.lines").read_text())["state"] == "host"
    assert json.loads((report / "down.lines").read_text())["state"] == "ok"
    assert any(line.startswith("FAIL down ") and f"exit {code}" in line for line in steps)


def test_rented_downs_failure_status_cannot_be_replaced_by_an_artifact_read_error(rented):
    """Prevent an error reading diagnostics from hiding the failure returned by the actual down process."""
    server = rented(down_rc=2, emit_failure=True)
    done = server.call()
    assert done.returncode == 2 and len(server.down_calls()) == 1
    report, steps = server.report()
    assert any(line.startswith("FAIL down ") and "exit 2" in line for line in steps)
    assert json.loads((report / "up.lines").read_text())["state"] == "host"


@pytest.mark.parametrize("reply_first", [False, True])
@pytest.mark.parametrize("received_signal", [signal.SIGINT, signal.SIGTERM, signal.SIGALRM])
def test_rented_signal_during_claim_cannot_abandon_owned_staging(rented, reply_first, received_signal):
    """Prevent an interrupted wait losing a completed claim and stranding the run's staging directory."""
    server = rented(claim_pause=True, claim_reply_first=reply_first)
    done = server.call(signal_at="claim-sleeping", signal_number=received_signal)
    assert done.returncode != 0
    assert not (server.guest / "run/porelo-rehearsal").exists()
    assert not server.events("check") and not server.down_calls()
    assert len(server.events("ssh")) == 2, "the confirmed claim must be followed by owner-checked cleanup"


def test_rented_signal_before_wait_stops_the_active_step_promptly(rented):
    """Prevent a signal handled immediately before wait from leaving the installation running until it finishes."""
    server = rented(up_sleep=True)
    done = server.call(signal_before_wait="up")
    assert done.returncode != 0 and len(server.down_calls()) == 1
    assert all(process.poll() is not None for process in server.jobs)


@pytest.mark.parametrize("unit_state", ["inactive", "failed"])
def test_rented_stopped_transient_units_cannot_block_down_and_are_reset(rented, unit_state):
    """Prevent a stopped failed unit from bypassing down or leaving its failed state behind."""
    server = rented(retained_unit_state=unit_state)
    done = server.call()
    assert done.returncode == 0, done.stderr
    assert len(server.down_calls()) == 1
    assert (server.base / "unit-reset").exists()
    stopped = next(row for row in server.events("systemctl") if row["args"][0] == "stop")
    reset = next(row for row in server.events("systemctl") if row["args"][0] == "reset-failed")
    assert reset["args"][1] == stopped["args"][1]


@pytest.mark.parametrize("check_failed", [False, True])
def test_rented_skipped_down_deletion_line_cannot_claim_the_playbook_ran(rented, check_failed):
    """Prevent the deletion instruction claiming down ran or packages were installed when neither happened."""
    server = rented(**({"check_failure": True} if check_failed else {"before_inventory": True}))
    done = server.call()
    assert done.returncode != 0 and not server.down_calls()
    report, steps = server.report()
    final = steps[-1]
    assert final == done.stderr.splitlines()[-1]
    assert "the host's down ran" not in final
    assert (server.guest / "packages").exists() is not check_failed
    if check_failed:
        assert "check failed before up" in final and "up installed no packages" in final
    else:
        assert "up did not reach its inventory" in final and "packages" in final


def test_rented_interrupted_inventory_write_cannot_publish_an_unstarted_host(rented):
    """Prevent cleanup using a half-written inventory before the up playbook can start."""
    server = rented(inventory_pause=True)
    done = server.call(signal_at="inventory-sleeping")
    assert done.returncode != 0 and not server.down_calls()
    assert not (server.guest / "root/porelo-host-inventory.yml").exists()
    assert (server.guest / "root/porelo-host-inventory.yml.tmp").stat().st_size > 0


@pytest.mark.parametrize("failure", ["check_upload_failure", "check_transport_error"])
def test_rented_check_errors_cannot_point_at_missing_or_empty_findings(rented, failure):
    """Prevent an installation failure directing diagnosis away from the log containing its real error."""
    server = rented(**{failure: True})
    done = server.call()
    assert done.returncode != 0
    report, steps = server.report()
    assert (report / "check.log").stat().st_size > 0
    assert any(line.startswith("FAIL check ") and str(report / "check.log") in line for line in steps)


@pytest.mark.parametrize("write", ["collection", "machine"])
def test_rented_prepare_writes_cannot_overwrite_another_owners_files(rented, write):
    """Prevent ownership changing between setup commands from overwriting a foreign collection or machine file."""
    server = rented(steal_before_write=write)
    machine = server.base / "machine.yml"
    machine.write_text("organization: {}\n")
    done = server.call("--machine-file", str(machine))
    assert done.returncode != 0 and not server.down_calls()
    assert (server.guest / "run/porelo-rehearsal/owner").read_text() == "another-run\n"
    if write == "collection":
        assert (server.guest / "run/porelo-rehearsal/porelo-host.tar.gz").read_text() == "foreign collection\n"
    else:
        assert (server.guest / "etc/porelo-host/setup/machine.yml").read_text() == "foreign machine\n"


def test_rented_pending_signal_is_checked_again_before_waiting_on_a_new_step(tmp_path):
    """Prevent a signal received before child launch from waiting for work that should be aborted."""
    library = tmp_path / "library.sh"
    source = REHEARSE.read_text().split("\n[ $# -ge 1 ] || usage\n")[0]
    library.write_text(source.replace("rented_abort_pending() {", "original_abort_pending() {", 1))
    report = tmp_path / "report"
    report.mkdir()
    waited = tmp_path / "wait-entered"
    code = f""". {shlex.quote(str(library))}
report={shlex.quote(str(report))}
pending_code=0 pending_reason='' current='' last_step='' active='' hook_sent=no
rented_abort_pending() {{
    original_abort_pending
    if [ "$hook_sent" = no ]; then hook_sent=yes; rented_signal TERM 143; fi
}}
wait() {{ printf waited > {shlex.quote(str(waited))}; command wait "$@"; }}
cleanup() {{
    status=$?
    trap - EXIT
    if [ -n "$active" ]; then stop_tree "$active"; command wait "$active" || true; fi
    exit "$status"
}}
trap cleanup EXIT
rented_step up 'start a child only with no pending signal' sleep 30
"""
    process = subprocess.Popen(
        ["sh", "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True
    )
    try:
        stdout, stderr = process.communicate(timeout=3)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        pytest.fail("a pending signal entered wait for a newly launched child")
    assert process.returncode == 143, stdout + stderr
    assert not waited.exists()


PHASE_TWO_STEPS = [
    "OK refuse-existing",
    "OK check",
    "OK up",
    "OK org",
    "OK project",
    "OK stop",
    "OK host-program",
    "SKIP tasks",
    "SKIP busy-room",
    "SKIP judge",
    "SKIP window",
    "OK push-pull",
    "OK refused-token",
    "OK org-follow",
    "OK org-off",
    "OK down",
    "OK read-keys",
    "delete the server",
]


def org_key(server, text="ssh-ed25519 AAAAORG test-operator\n"):
    path = server.base / "org.pub"
    if not path.exists():
        path.write_text(text)
    return path


def phase_two(server, *extra, **call):
    import socket

    agent = server.base / "agent.sock"
    if not agent.exists():
        listener = socket.socket(socket.AF_UNIX)
        listener.bind(str(agent))
        server.agent = listener
    server.environment["PORELO_REHEARSAL_FOLLOW_TRIES"] = "3"
    server.environment["PORELO_REHEARSAL_FOLLOW_PAUSE"] = "0"
    return server.call(
        "--org",
        str(server.bin / "org-program"),
        "--org-key",
        str(org_key(server)),
        "--person",
        "test-person",
        "--person-agent",
        str(agent),
        "--central-token",
        str(server.bin / "central-token"),
        "--project",
        "foo-project",
        *extra,
        **call,
    )


def test_rented_phase_two_runs_every_step_in_order_and_leaves_the_organization(rented):
    """Prevent a phase-2 step skipped silently, or the host left in the test organization."""
    server = rented()
    done = phase_two(server, "--retire-host", "machines-foo")
    assert done.returncode == 0, done.stderr
    steps = server.report()[1]
    assert [next(p for p in PHASE_TWO_STEPS if line.startswith(p + " ")) for line in steps] == PHASE_TWO_STEPS, steps
    org = [row["args"][2:] for row in server.events("org")]
    verbs = [arguments[0] for arguments in org]
    assert verbs == ["uncarry", "remove", "add", "change", "carry", "refresh", "uncarry", "remove"], org
    assert org[0][-2:] == ["machines-foo", "foo-project"] and org[1][-1] == "machines-foo"
    assert "--admin=test-person" in org[2] and org[2][-1] == "rented"
    assert {"--address=192.0.2.10", "--ssh-port=22", "--forge-web-port=3000", "--forge-git-port=3001"} <= set(org[3])
    assert "--host-key=ssh-ed25519 AAAAHOST" in org[3]
    assert org[4][-2:] == ["rented", "foo-project"] and org[6][-2:] == ["rented", "foo-project"]
    assert all(any(a.startswith("--id") for a in arguments) for arguments in org if arguments[0] != "refresh")


def test_rented_phase_two_hands_secrets_on_standard_input_alone(rented):
    """Prevent the vault passphrase or the central token reaching an argument list, the report or the output."""
    server = rented()
    done = phase_two(server)
    assert done.returncode == 0, done.stderr
    porelo = server.events("porelo")
    stop = next(row for row in porelo if row["args"][:2] == ["host", "stop-secrets"])
    assert stop["args"] == ["host", "stop-secrets", "--stdin", "vault-new"] and stop["stdin_lines"] == ["vault-new"]
    put = next(row for row in porelo if row["args"][:2] == ["vault", "put"])
    assert put["args"][-1] == "rented.localhost.central" and put["stdin_has_token"]
    assert all(row["args"][:2] == ["vault", "put"] for row in porelo if row["stdin_has_token"])
    events = (server.base / "events").read_text()
    report = server.report()[0]
    written = events + done.stdout + done.stderr + "".join(f.read_text() for f in report.iterdir() if f.is_file())
    assert "synthetic-central-token" not in written
    ssh = [row for row in server.events("ssh") if row["args"][row["args"].index("--") + 1].startswith("test-person@")]
    assert ssh and all(f"IdentityAgent={server.base / 'agent.sock'}" in row["args"] for row in ssh)
    assert all("StrictHostKeyChecking=yes" in row["args"] and "IdentityFile=none" in row["args"] for row in ssh)
    encoded = (server.base / "given-passphrase").read_text()
    passphrase = base64.b64decode(encoded).decode().strip()
    assert len(passphrase) >= 40 and encoded not in written and passphrase not in written


def test_rented_phase_two_waits_for_the_follow_to_admit_the_person(rented):
    """Prevent the stop running before the follow made the person's account."""
    server = rented(admitted_after=3)
    done = phase_two(server)
    assert done.returncode == 0, done.stderr
    assert len([row for row in server.events("porelo-host") if row["args"][:2] == ["org", "status"]]) == 3


def test_rented_phase_two_fails_when_the_follow_never_admits_and_still_leaves_the_organization(rented):
    """Prevent a run that waits for ever, or ends with the host still in the organization."""
    server = rented(admitted_after=99)
    done = phase_two(server)
    assert done.returncode != 0
    steps = server.report()[1]
    assert any(line.startswith("FAIL project ") for line in steps), steps
    assert not server.events("porelo"), "nothing is asked as the person before the follow admits them"
    assert any(line.startswith("OK org-off ") for line in steps), steps
    assert [row["args"][2] for row in server.events("org")][-2:] == ["uncarry", "remove"]


def test_rented_phase_two_names_the_host_left_in_the_organization(rented):
    """Prevent a failed removal passing unnoticed."""
    server = rented(org_rc={"remove": 65})
    done = phase_two(server)
    assert done.returncode == 65
    steps = server.report()[1]
    assert any(line.startswith("FAIL org-off ") for line in steps), steps
    assert any(line.startswith("LEFT in the organization") for line in steps), steps


def test_rented_phase_two_takes_off_only_what_it_put_on(rented):
    """Prevent an uncarry of a project the run never carried when the add itself failed."""
    server = rented(org_rc={"carry": 65})
    done = phase_two(server)
    assert done.returncode == 65
    assert [row["args"][2] for row in server.events("org")] == ["add", "change", "carry", "uncarry", "remove"]
    steps = server.report()[1]
    assert any(line.startswith("FAIL org ") for line in steps) and any(line.startswith("OK org-off ") for line in steps)


def test_rented_phase_two_removes_a_host_whose_add_failed_half_way(rented):
    """Prevent an add that wrote the card but answered an error leaving the host in the organization."""
    server = rented(org_rc={"add": 65})
    done = phase_two(server)
    assert done.returncode == 65
    assert [row["args"][2] for row in server.events("org")] == ["add", "remove"]


def test_rented_phase_two_keeps_the_first_failure_as_the_exit(rented):
    """Prevent a later org-off failure hiding the step that failed first."""
    server = rented(admitted_after=99, org_rc={"remove": 65})
    done = phase_two(server)
    assert done.returncode == 1
    steps = server.report()[1]
    assert any(line.startswith("FAIL project ") for line in steps) and any(
        line.startswith("FAIL org-off ") for line in steps
    )


def test_rented_phase_two_refuses_a_failed_central_token_program(rented):
    """Prevent an empty central token stored in the person's vault as if it were one."""
    server = rented(central_token_rc=3)
    done = phase_two(server)
    assert done.returncode != 0
    assert "the central token program gives no token" in done.stderr, done.stderr
    assert not server.events("ssh")
    assert not [row for row in server.events("porelo") if row["args"][:2] == ["vault", "put"]]


def test_rented_phase_two_leaves_the_organization_after_a_failed_down(rented):
    """Prevent a failed down skipping the organization's clean-up."""
    server = rented(down_rc=2)
    done = phase_two(server)
    assert done.returncode == 2
    assert (server.state / "known_hosts").exists() and not (server.state / "vault-passphrase").exists()
    steps = server.report()[1]
    assert any(line.startswith("FAIL down ") for line in steps) and any(
        line.startswith("OK org-off ") for line in steps
    )


@pytest.mark.parametrize(
    "missing", ["--org", "--org-key", "--person", "--person-agent", "--central-token", "--project"]
)
def test_rented_phase_two_refuses_a_partial_set_before_any_ssh(rented, missing):
    """Prevent half a phase 2 run against a real server."""
    server = rented()
    given = {
        "--org": str(server.bin / "org-program"),
        "--org-key": str(org_key(server)),
        "--person": "test-person",
        "--person-agent": str(server.base / "agent.sock"),
        "--central-token": str(server.bin / "central-token"),
        "--project": "foo-project",
    }
    del given[missing]
    done = server.call(*[part for pair in given.items() for part in pair])
    assert done.returncode != 0 and "phase 2 needs" in done.stderr
    assert not server.events("ssh")


@pytest.mark.parametrize("option", ["--person", "--project", "--retire-host"])
@pytest.mark.parametrize("value", ["-oProxyCommand=x", "Me", "a b", "rented/x"])
def test_rented_phase_two_refuses_a_name_that_is_not_plain(rented, option, value):
    """Prevent a login, project or host becoming an ssh or porelo option or another host's address."""
    server = rented()
    given = {"--person": "test-person", "--project": "foo-project", option: value}
    done = server.call(
        "--org",
        str(server.bin / "org-program"),
        "--org-key",
        str(org_key(server)),
        "--person-agent",
        str(server.base),
        "--central-token",
        str(server.bin / "central-token"),
        *[part for pair in given.items() for part in pair],
    )
    assert done.returncode != 0 and "not a plain name" in done.stderr and not server.events("ssh")


@pytest.mark.parametrize("case", ["own-host", "no-socket"])
def test_rented_phase_two_refuses_its_own_host_to_retire_and_an_agent_that_is_no_socket(rented, case):
    """Prevent the run removing its own card first, or ssh falling back to keys other than the person's agent."""
    server = rented()
    agent = server.base / "agent.sock"
    if case == "no-socket":
        agent.write_text("not a socket\n")
        extra = []
    else:
        import socket

        server.agent = socket.socket(socket.AF_UNIX)
        server.agent.bind(str(agent))
        extra = ["--retire-host", "rented"]
    done = server.call(
        "--org",
        str(server.bin / "org-program"),
        "--org-key",
        str(org_key(server)),
        "--person",
        "test-person",
        "--person-agent",
        str(agent),
        "--central-token",
        str(server.bin / "central-token"),
        "--project",
        "foo-project",
        *extra,
    )
    assert done.returncode != 0 and not server.events("ssh")
    assert ("own" in done.stderr) if case == "own-host" else ("no agent socket" in done.stderr)


def test_rented_phase_two_holds_the_host_up_until_the_hold_file_goes(rented):
    """Prevent down coming before another agent's live run on the same host has ended."""
    import threading

    server = rented()
    hold = server.base / "hold"
    server.environment["PORELO_REHEARSAL_HOLD_FILE"] = str(hold)
    seen = {}

    def release():
        deadline = time.monotonic() + 8
        while not hold.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        time.sleep(0.3)
        seen["held"] = hold.exists()
        seen["down_before"] = len(server.down_calls())
        hold.unlink()

    releaser = threading.Thread(target=release)
    releaser.start()
    done = phase_two(server)
    releaser.join()
    assert done.returncode == 0, done.stderr
    assert seen == {"held": True, "down_before": 0}
    steps = server.report()[1]
    assert [line.split(" ", 2)[1] for line in steps if line.startswith(("OK ", "HOLD "))][-8:] == [
        "push-pull",
        "refused-token",
        "hold",
        "hold",
        "org-follow",
        "org-off",
        "down",
        "read-keys",
    ], steps


def test_rented_phase_two_hard_stop_ends_a_hold_with_down(rented):
    """Prevent a forgotten hold file keeping a rented server past its hard stop."""
    server = rented()
    hold = server.base / "hold"
    server.environment["PORELO_REHEARSAL_HOLD_FILE"] = str(hold)
    done = phase_two(server, hard_stop=12, timeout=30)
    assert done.returncode == 124
    steps = server.report()[1]
    assert any(line.startswith("FAIL hold ") for line in steps), steps
    assert len(server.down_calls()) == 1 and any(line.startswith("OK org-off ") for line in steps)


def test_rented_phase_two_refuses_a_hold_file_that_is_already_there(rented):
    """Prevent two runs sharing one hold, or a hold writing through another file."""
    server = rented()
    hold = server.base / "hold"
    hold.write_text("another run's\n")
    server.environment["PORELO_REHEARSAL_HOLD_FILE"] = str(hold)
    done = phase_two(server)
    assert done.returncode != 0 and "hold file" in done.stderr and not server.events("ssh")
    assert hold.read_text() == "another run's\n"


def test_rented_phase_two_lets_the_operator_in_as_root_before_the_refresh(rented):
    """Prevent the refresh, which logs in as root, being refused for want of the operator's key (195.154.103.114)."""
    server = rented()
    done = phase_two(server)
    assert done.returncode == 0, done.stderr
    keys = (server.guest / "etc/ssh/authorized_keys/root").read_text().splitlines()
    assert keys == ["ssh-ed25519 AAAATEST", "ssh-ed25519 AAAAORG"], keys


def test_rented_phase_two_adds_the_operators_key_once(rented):
    """Prevent a second line for a key root already takes, as after a follow wrote the host admins' keys."""
    server = rented(root_keys="ssh-ed25519 AAAAORG somebody\n")
    done = phase_two(server)
    assert done.returncode == 0, done.stderr
    assert (server.guest / "etc/ssh/authorized_keys/root").read_text() == "ssh-ed25519 AAAAORG somebody\n"


def test_rented_phase_two_fails_org_when_up_left_no_root_key_file(rented):
    """Prevent the rehearsal making the file up owns, or carrying on to a refresh that cannot log in."""
    server = rented(no_root_keys=True)
    done = phase_two(server)
    assert done.returncode != 0
    steps = server.report()[1]
    assert any(line.startswith("FAIL org ") for line in steps), steps
    assert not (server.guest / "etc/ssh/authorized_keys/root").exists()
    assert not server.events("org"), "nothing is put into the organization for a host root cannot be reached on"


@pytest.mark.parametrize(
    "text",
    [
        "",
        "ssh-rsa AAAAB3Nza test\n",
        "ssh-ed25519 AAAAORG\nssh-ed25519 AAAAOTHER\n",
        "ssh-ed25519 AAAA;rm\n",
        "ssh-ed25519\n",
        "-----BEGIN OPENSSH PRIVATE KEY-----\n",
    ],
)
def test_rented_phase_two_refuses_an_operator_key_that_is_not_one_ed25519_public_key(rented, text):
    """Prevent a private key, a second key or shell text reaching root's keys on the host."""
    server = rented()
    org_key(server, text)
    done = phase_two(server)
    assert done.returncode != 0 and "operator key" in done.stderr and not server.events("ssh")


def test_rented_phase_two_keeps_roots_last_key_whole_when_its_file_has_no_newline_at_the_end(rented):
    """Prevent the operator's key glued to root's last line, which would spoil both keys."""
    server = rented(root_keys="ssh-ed25519 AAAATEST")
    done = phase_two(server)
    assert done.returncode == 0, done.stderr
    assert (server.guest / "etc/ssh/authorized_keys/root").read_text() == "ssh-ed25519 AAAATEST\nssh-ed25519 AAAAORG\n"


def test_rented_phase_two_takes_an_operator_key_file_without_a_newline_at_the_end(rented):
    """Prevent a one-line public key refused as if it were several lines."""
    server = rented()
    org_key(server, "ssh-ed25519 AAAAORG test-operator")
    done = phase_two(server)
    assert done.returncode == 0, done.stderr
    assert "ssh-ed25519 AAAAORG" in (server.guest / "etc/ssh/authorized_keys/root").read_text().splitlines()


def held(server, then, timeout=20, **call):
    """Run phase 2 with a hold file and act once the failure hold has made it."""
    import threading

    hold = server.base / "hold"
    server.environment["PORELO_REHEARSAL_HOLD_FILE"] = str(hold)
    seen = {}

    def act():
        deadline = time.monotonic() + timeout - 5
        while not hold.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        time.sleep(0.3)
        seen["held"] = hold.exists()
        seen["down_before"] = len(server.down_calls())
        then(server, hold)

    actor = threading.Thread(target=act)
    actor.start()
    done = phase_two(server, timeout=timeout, **call)
    actor.join()
    return done, seen


def admit(server):
    settings = json.loads((server.base / "answers.json").read_text())
    settings.pop("admitted_after", None)
    (server.base / "answers.json").write_text(json.dumps(settings))


def test_rented_phase_two_holds_the_host_up_after_a_failed_step_until_the_hold_file_goes(rented):
    """Prevent a failure in minute 5 taking the rented host down before it can be fixed on the same server."""
    server = rented(admitted_after=99)
    done, seen = held(server, lambda server, hold: hold.unlink())
    assert done.returncode == 1, done.stderr
    assert seen == {"held": True, "down_before": 0}
    steps = server.report()[1]
    marks = [line.split(" ", 2)[0] + " " + line.split(" ", 2)[1] for line in steps]
    assert marks[marks.index("FAIL project") :][:4] == [
        "FAIL project",
        "HOLD failure",
        "OK org-follow",
        "OK org-off",
    ], steps
    assert len(server.down_calls()) == 1


def test_rented_phase_two_resumes_a_held_run_from_up_and_its_failed_step(rented):
    """Prevent a fixed rerun needing a new server, or repeating steps that passed in the held run."""
    server = rented(admitted_after=99)

    def resume(server, hold):
        admit(server)
        request = Path(str(hold) + ".resume")
        request.write_text("")
        deadline = time.monotonic() + 15
        while (request.exists() or not hold.exists()) and time.monotonic() < deadline:
            time.sleep(0.01)
        time.sleep(0.3)
        hold.unlink()

    done, seen = held(server, resume)
    assert done.returncode == 0, done.stderr
    assert seen == {"held": True, "down_before": 0}
    steps = server.report()[1]
    marks = [line.split(" ", 2)[0] + " " + line.split(" ", 2)[1] for line in steps]
    after = marks[marks.index("FAIL project") :]
    assert after[:18] == [
        "FAIL project",
        "HOLD failure",
        "RESUME the",
        "OK up",
        "OK project",
        "OK stop",
        "OK host-program",
        "SKIP tasks",
        "SKIP busy-room",
        "SKIP judge",
        "SKIP window",
        "OK push-pull",
        "OK refused-token",
        "HOLD hold",
        "OK hold",
        "OK org-follow",
        "OK org-off",
        "OK down",
    ], steps
    assert [row["args"][2] for row in server.events("org")] == [
        "add",
        "change",
        "carry",
        "refresh",
        "refresh",
        "uncarry",
        "remove",
    ]
    assert len([row for row in server.events("ansible-playbook") if row["verb"] == "up"]) == 2
    hold = server.base / "hold"
    assert not hold.exists() and not Path(str(hold) + ".resume").exists()
    assert not (server.state / "resume.env").exists()


@pytest.mark.parametrize("request_text", ["PORELO_HOST_DEB=/nowhere/porelo-host.deb\n", "rm -rf /\n", "X=1\n"])
def test_rented_phase_two_refuses_a_resume_file_it_cannot_take_and_stays_held(rented, request_text):
    """Prevent a resume file running shell text, or a resume with packages that are not there."""
    server = rented(admitted_after=99)

    def refuse_then_release(server, hold):
        request = Path(str(hold) + ".resume")
        request.write_text(request_text)
        deadline = time.monotonic() + 8
        while request.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        time.sleep(0.3)
        hold.unlink()

    done, seen = held(server, refuse_then_release)
    assert done.returncode == 1, done.stderr
    steps = server.report()[1]
    assert any(line.startswith("FAIL resume ") and "stays held" in line for line in steps), steps
    assert not any(line.startswith("RESUME ") for line in steps), steps
    assert len(server.down_calls()) == 1


def test_rented_phase_two_hard_stop_ends_a_failure_hold_with_down(rented):
    """Prevent a forgotten failure hold keeping a rented server past its hard stop."""
    server = rented(admitted_after=99)
    hold = server.base / "hold"
    server.environment["PORELO_REHEARSAL_HOLD_FILE"] = str(hold)
    done = phase_two(server, hard_stop=12, timeout=30)
    assert done.returncode == 124
    steps = server.report()[1]
    assert any(line.startswith("HOLD failure ") for line in steps), steps
    assert any(line.startswith("FAIL hold ") for line in steps), steps
    assert len(server.down_calls()) == 1 and any(line.startswith("OK org-off ") for line in steps)


def test_rented_a_failed_check_is_not_held(rented):
    """Prevent a server unfit for the host being held: there is nothing on it to fix."""
    server = rented(check_failure=True)
    server.environment["PORELO_REHEARSAL_HOLD_FILE"] = str(server.base / "hold")
    done = phase_two(server)
    assert done.returncode != 0
    steps = server.report()[1]
    assert not any(line.startswith("HOLD ") for line in steps), steps
    assert not (server.base / "hold").exists()


@pytest.mark.parametrize(
    "case",
    ["packages-alone", "script-not-executable"],
)
def test_rented_phase_two_refuses_a_resume_that_could_not_take_effect_and_stays_held(rented, case):
    """Prevent a resume whose packages are ignored, or one that leaves the host without its down when it cannot start."""
    server = rented(admitted_after=99)
    packages = server.base / "packages"
    packages.mkdir()

    def refuse_then_release(server, hold):
        request = Path(str(hold) + ".resume")
        if case == "script-not-executable":
            server.script.chmod(0o644)
            request.write_text("")
        else:
            request.write_text(f"PORELO_HOST_PACKAGES={packages}\n")
        deadline = time.monotonic() + 8
        while request.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        time.sleep(0.3)
        hold.unlink()

    done, seen = held(server, refuse_then_release)
    assert done.returncode == 1, done.stderr
    steps = server.report()[1]
    assert any(line.startswith("FAIL resume ") and "stays held" in line for line in steps), steps
    assert not any(line.startswith("RESUME ") for line in steps), steps
    assert len(server.down_calls()) == 1


def test_rented_phase_two_resume_takes_the_new_collection_beside_an_old_one(rented):
    """Prevent a fixed collection of a new version failing the rerun up as an ambiguous tarball."""
    server = rented(admitted_after=99)

    def resume(server, hold):
        admit(server)
        (server.state / "porelo-host-old.tar.gz").write_text("an older build\n")
        request = Path(str(hold) + ".resume")
        request.write_text("")
        deadline = time.monotonic() + 15
        while (request.exists() or not hold.exists()) and time.monotonic() < deadline:
            time.sleep(0.01)
        time.sleep(0.3)
        hold.unlink()

    done, seen = held(server, resume)
    assert done.returncode == 0, done.stderr
    assert sum(line.startswith("OK up ") for line in server.report()[1]) == 2


def test_rented_phase_two_resume_after_the_stop_reruns_the_project_step_but_not_the_stop(rented):
    """Prevent a step after the follow running on a host whose rerun up was not followed again."""
    server = rented(porelo_rc={"pull": 70})

    def resume(server, hold):
        settings = json.loads((server.base / "answers.json").read_text())
        settings.pop("porelo_rc")
        (server.base / "answers.json").write_text(json.dumps(settings))
        request = Path(str(hold) + ".resume")
        request.write_text("")
        deadline = time.monotonic() + 15
        while (request.exists() or not hold.exists()) and time.monotonic() < deadline:
            time.sleep(0.01)
        time.sleep(0.3)
        hold.unlink()

    done, seen = held(server, resume)
    assert done.returncode == 0, done.stderr
    steps = server.report()[1]
    marks = [line.split(" ", 2)[0] + " " + line.split(" ", 2)[1] for line in steps]
    after = marks[marks.index("RESUME the") :]
    assert after[:3] == ["RESUME the", "OK up", "OK project"] and after[3] == "OK push-pull", steps
    assert len([row for row in server.events("porelo") if row["args"][:2] == ["host", "stop-secrets"]]) == 1
