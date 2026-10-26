"""Exercise the gathered push against local repositories standing in for both forges."""

import base64
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "roles/forge/files/porelo-host-push"
ADMIN_TOKEN = "admin-token-4f1c9e"
CENTRAL_TOKEN = "central-token-7b2d5a"
GIT = shutil.which("git")
IDENTITY = {
    "GIT_AUTHOR_NAME": "Fixture",
    "GIT_AUTHOR_EMAIL": "fixture@example.org",
    "GIT_COMMITTER_NAME": "Fixture",
    "GIT_COMMITTER_EMAIL": "fixture@example.org",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_NOSYSTEM": "1",
}


def git(*args, cwd=None):
    result = subprocess.run(
        [GIT, *args], cwd=cwd, env={**os.environ, **IDENTITY}, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, f"fixture git {args} failed: {result.stderr}"
    return result.stdout.strip()


def commit(repository, work, name):
    """Commits the file `name` on main of the bare `repository` and returns the commit's id."""
    shutil.rmtree(work, ignore_errors=True)
    if git("--git-dir", str(repository), "for-each-ref", "refs/heads/main"):
        git("clone", "--quiet", "--branch", "main", str(repository), str(work))
    else:
        git("init", "--quiet", "--initial-branch=main", str(work))
        git("remote", "add", "origin", str(repository), cwd=work)
    (work / name).write_text(name + "\n")
    git("add", name, cwd=work)
    git("commit", "--quiet", "-m", f"Add {name}", cwd=work)
    git("push", "--quiet", "origin", "main", cwd=work)
    return git("rev-parse", "HEAD", cwd=work)


def bare(path, source=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if source is None:
        git("init", "--quiet", "--bare", "--initial-branch=main", str(path))
    else:
        git("clone", "--quiet", "--bare", str(source), str(path))
    return path


def moved(script, fixed, replacement):
    assert script.count(fixed) == 1, f"the command names {fixed!r} once"
    return script.replace(fixed, replacement)


@pytest.fixture
def host(tmp_path):
    """A host with both forges as local repositories, the command's paths moved into the fixture.

    The command starts again with an empty environment, so each stub has its paths written into it.
    """
    etc = tmp_path / "etc"
    etc.mkdir()
    (etc / "api.token").write_text(ADMIN_TOKEN + "\n")
    for ca in ("ca.pem", "central-ca.pem"):
        (etc / ca).write_text("")
        (etc / ca).chmod(0o644)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    temporary = tmp_path / "temporary"
    temporary.mkdir()
    calls = tmp_path / "calls"

    script = SCRIPT.read_text()
    script = moved(script, "/etc/porelo-host/forge/push.conf", str(etc / "push.conf"))
    script = moved(script, "/home/porelo-forge/.config/porelo-forge/api.token", str(etc / "api.token"))
    script = moved(script, "/etc/porelo-host/forge/ca.pem", str(etc / "ca.pem"))
    script = moved(script, "PATH=/usr/sbin:/usr/bin:/sbin:/bin", f"PATH={bin_dir}:/usr/sbin:/usr/bin:/sbin:/bin")
    script = moved(script, "work=$(mktemp -d)", f"work=$(mktemp -d -p {temporary})")
    script = moved(script, "ca_owner=0", f"ca_owner={os.getuid()}")
    command = tmp_path / "porelo-host-push"
    command.write_text(script)
    command.chmod(0o755)

    (bin_dir / "id").write_text(f"#!/bin/sh\ncat {tmp_path / 'uid'}\n")
    (tmp_path / "uid").write_text("0\n")
    # Run as the forge's account: here the same account, as long as the token file is readable to it.
    (bin_dir / "runuser").write_text('#!/bin/sh\nwhile [ "$1" != -- ]; do shift; done\nshift\nexec "$@"\n')
    (bin_dir / "git").write_text(
        "#!/bin/sh\n"
        f'printf \'%s|%s=%s|%s\\n\' "${{GIT_SSL_CAINFO:-}}" "${{GIT_CONFIG_KEY_1:-}}" "${{GIT_CONFIG_VALUE_1:-}}" "$*"'
        f" >> {calls}\n"
        'case " $* " in *" push "*)\n'
        f"    : > {tmp_path / 'pushing'}\n"
        f"    if [ -e {tmp_path / 'push-waits'} ]; then sleep 5; fi\n"
        f'    if [ -e {tmp_path / "push-says-header"} ]; then printf \'%s\\n\' "$GIT_CONFIG_VALUE_0" >&2; exit 128; fi\n'
        ";; esac\n"
        f'exec {GIT} "$@"\n'
    )
    for stub in ("id", "runuser", "git"):
        (bin_dir / stub).chmod(0o755)

    central = bare(tmp_path / "central" / "stand-in.git")
    commit(central, tmp_path / "seed", "README")
    local = bare(tmp_path / "local" / "porelo" / "stand-in.git", source=central)
    central_two = bare(tmp_path / "central" / "second.git")
    commit(central_two, tmp_path / "seed", "README")
    bare(tmp_path / "local" / "porelo" / "second.git", source=central_two)
    (etc / "push.conf").write_text(
        "# written by the role\n"
        f"local file://{tmp_path / 'local'}\n"
        "owner porelo\n"
        f"central-ca {etc / 'central-ca.pem'}\n"
        f"repository stand-in file://{central}\n"
        f"repository second file://{central_two}\n"
    )
    return {"root": tmp_path, "command": command, "temporary": temporary, "calls": calls, "local": local}


def push(host, *repositories, token=CENTRAL_TOKEN, environment=None, interrupt=False):
    process = subprocess.Popen(
        [str(host["command"]), *repositories],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env={"PATH": "/usr/bin:/bin", **(environment or {})},
        text=True,
        start_new_session=True,
    )
    if not interrupt:
        output, _ = process.communicate(token + "\n", timeout=60)
        return process.returncode, output
    process.stdin.write(token + "\n")
    process.stdin.close()
    deadline = time.monotonic() + 30
    while not (host["root"] / "pushing").exists():
        assert time.monotonic() < deadline, "the push never started"
        assert process.poll() is None, f"the command ended before its push: {process.stdout.read()}"
        time.sleep(0.05)
    # As a terminal's Ctrl+C does: the whole foreground group, git's children with it.
    os.killpg(process.pid, signal.SIGINT)
    output = process.stdout.read()
    return process.wait(timeout=30), output


def head(repository, branch="main"):
    return git("--git-dir", str(repository), "rev-parse", f"refs/heads/{branch}")


def assert_no_token_anywhere(host, output):
    calls = host["calls"].read_text() if host["calls"].exists() else ""
    for token in (ADMIN_TOKEN, CENTRAL_TOKEN):
        basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        for form in (token, basic):
            assert form not in output, f"a token was printed: {output}"
            assert form not in calls, f"a token reached a command line: {calls}"


def test_a_push_with_nothing_new_on_central_is_taken(host):
    """Prevents approved work from staying on the host when the central forge has not moved."""
    central = host["root"] / "central" / "stand-in.git"
    approved = commit(host["local"], host["root"] / "work", "B")

    code, output = push(host, "stand-in")

    assert code == 0, f"the push was refused with {code}: {output}"
    assert head(central) == approved, f"asked for central main {approved}, got {head(central)}"
    assert "stand-in: taken" in output, output
    assert_no_token_anywhere(host, output)
    assert list(host["temporary"].iterdir()) == [], "the temporary clone was left behind"


def test_a_moved_central_forge_refuses_keeps_both_and_brings_its_commits_back(host):
    """Prevents a push from erasing central work, and the central work from going unseen."""
    central = host["root"] / "central" / "stand-in.git"
    central_work = commit(central, host["root"] / "central-work", "A")
    local_main = commit(host["local"], host["root"] / "work", "C")

    code, output = push(host, "stand-in", "second")

    assert code != 0, f"a push over a moved central forge was taken: {output}"
    assert head(central) == central_work, f"central main lost {central_work}, holds {head(central)}"
    assert head(host["local"]) == local_main, f"local main moved from {local_main} to {head(host['local'])}"
    assert head(host["local"], "central/main") == central_work, "central main was not brought to the local forge"
    assert "Add A" in output, f"the refusal does not name the central commit: {output}"
    assert "not pushed either: second" in output, f"the refusal does not name what was left: {output}"
    second = host["root"] / "central" / "second.git"
    assert git("--git-dir", str(second), "log", "--format=%s", "-1", "main") == "Add README", "second was pushed"
    assert_no_token_anywhere(host, output)
    assert list(host["temporary"].iterdir()) == [], "the temporary clone was left behind"


def test_what_git_says_is_shown_without_a_token(host):
    """Prevents a token from reaching the terminal or its scrollback when git repeats a header."""
    commit(host["local"], host["root"] / "work", "B")
    (host["root"] / "push-says-header").touch()

    code, output = push(host, "stand-in")

    assert code != 0, f"a push that git failed was taken: {output}"
    assert "<redacted>" in output, f"git's own words were not shown: {output}"
    assert_no_token_anywhere(host, output)


def test_the_callers_git_settings_cannot_send_the_push_elsewhere(host):
    """Prevents root's push from following a destination its caller planted in the environment."""
    elsewhere = bare(host["root"] / "elsewhere" / "stand-in.git")
    central = host["root"] / "central" / "stand-in.git"
    approved = commit(host["local"], host["root"] / "work", "B")
    planted = f"'url.file://{elsewhere}.pushInsteadOf'='file://{central}'"

    code, output = push(host, "stand-in", environment={"GIT_CONFIG_PARAMETERS": planted})

    assert code == 0, f"the push was refused with {code}: {output}"
    assert head(central) == approved, f"asked for central main {approved}, got {head(central)}"
    assert not git("--git-dir", str(elsewhere), "for-each-ref"), "the push went where the caller said"


def test_each_forge_is_trusted_by_its_own_authority_and_no_redirect_is_followed(host):
    """Prevents the host's CA from vouching for the central forge, and a token sent on to a redirect's host."""
    commit(host["local"], host["root"] / "work", "B")
    etc = host["root"] / "etc"

    code, output = push(host, "stand-in")

    assert code == 0, f"the push was refused with {code}: {output}"
    calls = [line.split("|", 2) for line in host["calls"].read_text().splitlines()]
    remote = [call for call in calls if any(f" {verb} " in f" {call[2]} " for verb in ("clone", "push", "fetch"))]
    assert remote, f"no call reached a forge: {calls}"
    for ca, redirects, line in remote:
        assert redirects == "http.followRedirects=false", f"a forge call follows redirects: {line}"
        want = etc / ("ca.pem" if line.startswith("clone") else "central-ca.pem")
        assert ca == str(want), f"asked for {want} for {line!r}, got {ca!r}"


def test_a_token_file_put_in_place_of_standard_input_never_reads_the_central_token(host):
    """Prevents the forge's account from reading the person's central token through its own token file."""
    token_file = host["root"] / "etc" / "api.token"
    token_file.unlink()
    token_file.symlink_to("/dev/stdin")

    code, output = push(host, "stand-in")

    assert code == 66, f"asked for 66 on a token file read from standard input, got {code}: {output}"
    assert not host["calls"].exists(), "git ran with a token read from standard input"


def test_a_repository_the_forge_does_not_hold_is_refused_before_anything_is_read(host):
    """Prevents a push to a place the host's settings do not name."""
    code, output = push(host, "stand-in", "elsewhere")

    assert code == 64, f"asked for 64 on an unknown repository, got {code}: {output}"
    assert "elsewhere" in output, output
    assert "Token" not in output, f"the token was asked for before the names were checked: {output}"
    assert not host["calls"].exists(), "git ran before the names were checked"


def test_a_repository_named_twice_is_refused_before_anything_is_pushed(host):
    """Prevents a half-done run that pushed the first and failed on its second naming."""
    code, output = push(host, "stand-in", "stand-in")

    assert code == 64, f"asked for 64 on a repository named twice, got {code}: {output}"
    assert not host["calls"].exists(), "git ran before the names were checked"


def test_it_runs_only_as_root(host):
    """Prevents a run that would fail halfway on files only root reads."""
    (host["root"] / "uid").write_text("1000\n")

    code, output = push(host, "stand-in")

    assert code == 77, f"asked for 77 when not root, got {code}: {output}"
    assert not host["calls"].exists(), "git ran for an account that is not root"


def test_a_token_file_that_cannot_be_read_stops_the_push(host):
    """Prevents a push with no token of the forge's; that root reads it as the forge's account is Molecule's to show."""
    (host["root"] / "etc" / "api.token").chmod(0o000)

    code, output = push(host, "stand-in")

    assert code == 66, f"asked for 66 on an unreadable token, got {code}: {output}"
    assert not host["calls"].exists(), "git ran without the forge's token"


def test_an_interrupted_push_leaves_no_clone_behind_and_pushes_nothing(host):
    """Prevents a clone of private work left on the host, and a push that goes on after Ctrl+C."""
    central = host["root"] / "central" / "stand-in.git"
    before = head(central)
    commit(host["local"], host["root"] / "work", "B")
    (host["root"] / "push-waits").touch()

    code, output = push(host, "stand-in", interrupt=True)

    assert code == 130, f"asked for 130 after an interrupt, got {code}: {output}"
    assert head(central) == before, "the push went on after the interrupt"
    assert list(host["temporary"].iterdir()) == [], "the interrupted push left its clone behind"
