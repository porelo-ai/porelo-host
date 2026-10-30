"""Exercise the person's stop on a terminal without a host account or real credentials."""

import base64
import errno
import os
import pty
import select
import signal
import subprocess
import sys
import termios
import time
from contextlib import contextmanager
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "roles/porelo/files/porelo-host-stop"


@pytest.fixture
def terminal_home(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "id").write_text("#!/bin/sh\nprintf '4242\\n'\n")
    (bin_dir / "id").chmod(0o755)
    (bin_dir / "porelo").write_text(
        f"#!{sys.executable}\n"
        "import getpass, os, sys\n"
        "from pathlib import Path\n"
        "home = Path(os.environ['HOME'])\n"
        "if os.environ.get('XDG_RUNTIME_DIR') != '/run/user/4242':\n"
        "    sys.exit('the account runtime directory was not set')\n"
        "with (home / 'vault-called').open('a') as calls:\n"
        "    calls.write(' '.join(sys.argv[1:]) + '\\n')\n"
        "if sys.argv[1:] == ['vault', 'init']:\n"
        "    chosen = getpass.getpass('New vault passphrase: ')\n"
        "    again = getpass.getpass('New vault passphrase again: ')\n"
        "    if chosen != again:\n"
        "        sys.exit('porelo: the two did not match - no vault was created')\n"
        "    if not chosen:\n"
        "        sys.exit('porelo: an empty passphrase would leave the vault unprotected')\n"
        "    (home / 'vault-made').touch()\n"
        "elif sys.argv[1:] == ['vault', 'unlock']:\n"
        "    if getpass.getpass('Vault passphrase: ') != 'vault-passphrase':\n"
        "        sys.exit('porelo: that passphrase does not open the vault - nothing was cached')\n"
        "    (home / 'vault-open').touch()\n"
        "else:\n"
        "    sys.exit('unexpected vault command')\n"
    )
    (bin_dir / "porelo").chmod(0o755)
    return tmp_path


class Terminal:
    def __init__(self, pid, fd):
        self.pid = pid
        self.fd = fd
        self.output = b""
        self.pending = b""
        self.ended = False
        self.reaped = False

    def read(self, timeout):
        if self.ended or not select.select([self.fd], [], [], timeout)[0]:
            return
        try:
            data = os.read(self.fd, 65536)
        except OSError as error:
            if error.errno != errno.EIO:
                raise
            data = b""
        self.output += data
        self.pending += data
        self.ended = not data

    def expect(self, text):
        wanted = text.encode()
        deadline = time.monotonic() + 5
        while wanted not in self.pending and not self.ended and time.monotonic() < deadline:
            self.read(max(0, deadline - time.monotonic()))
        assert wanted in self.pending, f"expected terminal prompt {text!r}, got {self.output.decode()!r}"
        self.pending = self.pending.split(wanted, 1)[1]

    def send(self, text):
        os.write(self.fd, text.encode())

    def finish(self):
        deadline = time.monotonic() + 5
        while not self.ended and time.monotonic() < deadline:
            self.read(max(0, deadline - time.monotonic()))
        assert self.ended, f"the stop must exit instead of hanging; got {self.output.decode()!r}"
        _, status = os.waitpid(self.pid, 0)
        self.reaped = True
        return os.waitstatus_to_exitcode(status)


@contextmanager
def stop(home, *args):
    pid, fd = pty.fork()
    if pid == 0:
        # The client stand-in reads stdin without hiding it; dummy credentials must not echo.
        settings = termios.tcgetattr(0)
        settings[3] &= ~termios.ECHO
        termios.tcsetattr(0, termios.TCSANOW, settings)
        os.execve(
            "/bin/bash",
            ["bash", str(SCRIPT), *args],
            {"PATH": str(home / "bin"), "HOME": str(home), "TERM": "dumb"},
        )
    terminal = Terminal(pid, fd)
    try:
        yield terminal
    finally:
        if not terminal.reaped:
            try:
                os.killpg(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            os.waitpid(pid, 0)
        os.close(fd)


def test_new_vault_retries_until_both_passphrases_match(terminal_home):
    """Prevent mismatched passphrases from making a vault or reporting done while the host still waits."""
    home = terminal_home
    with stop(home, "vault-new") as terminal:
        terminal.expect("New vault passphrase: ")
        terminal.send("vault-passphrase\n")
        terminal.expect("New vault passphrase again: ")
        terminal.send("different\n")
        terminal.expect("Try again? [Y/n]")
        assert not (home / "vault-made").exists(), "mismatched passphrases must not create a vault"
        terminal.send("Y\n")
        terminal.expect("New vault passphrase: ")
        terminal.send("vault-passphrase\n")
        terminal.expect("New vault passphrase again: ")
        terminal.send("vault-passphrase\n")
        assert terminal.finish() == 0, "done requires the named need to have succeeded"
    assert (home / "vault-made").exists(), "success must leave a vault on the host"


@pytest.mark.parametrize("answer", ["n", "N"])
def test_declining_retry_leaves_no_vault(terminal_home, answer):
    """Prevent cancellation after a failed attempt from creating the vault."""
    home = terminal_home
    with stop(home, "vault-new") as terminal:
        terminal.expect("New vault passphrase: ")
        terminal.send("vault-passphrase\n")
        terminal.expect("New vault passphrase again: ")
        terminal.send("different\n")
        terminal.expect("Try again? [Y/n]")
        terminal.send(answer + "\n")
        assert terminal.finish() == 75, "declining retry must report cancellation"
    assert not (home / "vault-made").exists(), "cancellation must leave the vault absent"


def test_interrupting_the_passphrase_cancels_the_stop(terminal_home):
    """Prevent Ctrl+C at the passphrase from retrying or reporting done."""
    home = terminal_home
    with stop(home, "vault") as terminal:
        terminal.expect("Vault passphrase: ")
        terminal.send("\x03")
        assert terminal.finish() == 75, "Ctrl+C at a child's passphrase read must report cancellation"
    assert not (home / "vault-open").exists(), "an interrupted unlock must not open the vault"


def test_unlock_retries_a_wrong_passphrase(terminal_home):
    """Prevent a wrong unlock passphrase from reporting an open vault or ending the session."""
    home = terminal_home
    with stop(home, "vault") as terminal:
        terminal.expect("Vault passphrase: ")
        terminal.send("wrong\n")
        terminal.expect("Try again? [Y/n]")
        assert not (home / "vault-open").exists(), "a wrong passphrase must not open the vault"
        terminal.send("y\n")
        terminal.expect("Vault passphrase: ")
        terminal.send("vault-passphrase\n")
        assert terminal.finish() == 0, "the correct retry must complete the stop"
    assert (home / "vault-open").exists(), "success must leave the vault open"
    assert not (home / "vault-made").exists(), "unlock must not initialize a vault instead"


@pytest.mark.parametrize(
    "args, diagnostic",
    [
        (("vault", "nonsense"), "nonsense"),
        (("--email", "person@example.com", "vault"), "--email"),
        ((), "need"),
        (("drive",), "drive"),
        (("vault-new", "drive"), "drive"),
        (("--stdin", "drive"), "drive"),
        (("vault-new", "vault"), "exclude"),
        (("vault", "vault"), "twice"),
        # Run as the person, --stdin reads a pipe: a terminal would wait for lines nobody types.
        (("--stdin", "vault-new"), "pipe"),
        (("--stdin", "matrix-token"), "matrix-token"),
        (("--stdin", "identities", "identities"), "twice"),
        (("--stdin", "wireguard", "wireguard"), "unknown need"),
        (("matrix-token",), "matrix-token"),
    ],
)
def test_invalid_calls_run_no_command(terminal_home, args, diagnostic):
    """Prevent a malformed call from signing in or changing the vault before refusal."""
    home = terminal_home
    for path in (home / "bin").iterdir():
        path.unlink()
        path.write_text('#!/bin/sh\nprintf called >> "$HOME/called"\nexit 99\n')
        path.chmod(0o755)
    with stop(home, *args) as terminal:
        assert terminal.finish() == 64, "a malformed call must fail with the usage exit code"
    assert diagnostic in terminal.output.decode(), "the refusal must identify the invalid argument or missing need"
    assert not (home / "called").exists(), "validation must finish before any command on PATH runs"


@pytest.mark.parametrize("need, missing", [("vault", "porelo"), ("vault-new", "porelo")])
def test_missing_dependencies_fail_before_asking(terminal_home, need, missing):
    """Prevent an unavailable client or vault command from hanging in a retry loop."""
    home = terminal_home
    (home / "bin" / missing).unlink()
    with stop(home, need) as terminal:
        assert terminal.finish() == 69, "a missing command must report an unavailable dependency"
    assert missing in terminal.output.decode(), "the refusal must name the missing command"
    assert not (home / "vault-called").exists(), "a missing dependency must not reach the vault"


@pytest.fixture
def own_account(tmp_path):
    """A person's account: a stand-in Porelo that records each call and what it read, and their runtime directory."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "porelo").write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "call = {'args': sys.argv[1:], 'stdin': sys.stdin.read(), 'runtime': os.environ.get('XDG_RUNTIME_DIR')}\n"
        "with (Path(os.environ['HOME']) / 'porelo-calls').open('a') as calls:\n"
        "    calls.write(json.dumps(call) + '\\n')\n"
        "sys.exit(int(os.environ.get('PORELO_STUB_EXIT', '0')))\n"
    )
    (bin_dir / "porelo").chmod(0o755)
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    return tmp_path


def own_stop(home, *needs, lines="", extra=None):
    environment = {"PATH": f"{home / 'bin'}:/usr/bin:/bin", "HOME": str(home), "XDG_RUNTIME_DIR": str(home / "runtime")}
    environment.update(extra or {})
    return subprocess.run(
        ["bash", str(SCRIPT), "--stdin", *needs],
        input=lines,
        capture_output=True,
        text=True,
        env=environment,
        timeout=20,
        check=False,
    )


def calls(home):
    import json

    path = home / "porelo-calls"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def b64(text):
    return base64.b64encode(text.encode()).decode()


def test_the_person_opens_a_new_vault_and_puts_keys_from_their_own_pipe(own_account):
    """Prevent the person's secrets from passing through root or any file on their way into their own vault."""
    home = own_account
    lines = f"vault-new {b64('chosen passphrase')}\nkey signing.key {b64('KEY MATERIAL')}\n"
    result = own_stop(home, "vault-new", "keys", lines=lines)
    assert result.returncode == 0, result.stderr
    assert [call["args"] for call in calls(home)] == [
        ["vault", "init", "--passphrase-stdin"],
        ["vault", "put", "signing.key"],
    ]
    assert [call["stdin"] for call in calls(home)] == ["chosen passphrase", "KEY MATERIAL"]
    assert all(call["runtime"] == str(home / "runtime") for call in calls(home))
    output = result.stdout + result.stderr
    assert "chosen passphrase" not in output and "KEY MATERIAL" not in output


def waiting_bring(home, project="alpha"):
    """The bring's list of repositories to migrate, and a stand-in migration recording its call and its input."""
    push_dir = home / ".config/porelo-host/push"
    push_dir.mkdir(parents=True, exist_ok=True)
    (push_dir / f"{project}.migrate").write_text("owner alpha\n")
    (home / "bin/porelo-host-push").write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "call = {'args': sys.argv[1:], 'stdin': sys.stdin.read()}\n"
        "(Path(os.environ['HOME']) / 'push-calls').write_text(json.dumps(call))\n"
        "sys.exit(int(os.environ.get('PUSH_STUB_EXIT', '0')))\n"
    )
    (home / "bin/porelo-host-push").chmod(0o755)


def test_the_central_forge_token_goes_on_a_pipe_into_the_migration_alone(own_account):
    """Prevent the central forge's token from lying in any file on the host, even for the length of a bring."""
    home = own_account
    waiting_bring(home)
    result = own_stop(home, "forge-central-token", lines=f"forge-central-token {b64('central-token')}\n")
    assert result.returncode == 0, result.stderr
    import json

    assert json.loads((home / "push-calls").read_text()) == {"args": ["--migrate", "alpha"], "stdin": "central-token"}
    files = [path for path in home.rglob("*") if path.is_file() and path.name != "push-calls"]
    assert not [path for path in files if b"central-token" in path.read_bytes()], "the token lies in a file"
    assert "central-token" not in result.stdout + result.stderr
    assert calls(home) == []


def test_the_central_token_without_a_waiting_bring_is_refused(own_account):
    """Prevent the token from being taken when no bring waits for it, or two do and the stop cannot say which."""
    home = own_account
    waiting_bring(home)
    (home / ".config/porelo-host/push/alpha.migrate").unlink()
    result = own_stop(home, "forge-central-token", lines=f"forge-central-token {b64('central-token')}\n")
    assert result.returncode == 69 and "no single bring waits" in result.stderr
    waiting_bring(home, "beta")
    waiting_bring(home, "gamma")
    result = own_stop(home, "forge-central-token", lines=f"forge-central-token {b64('central-token')}\n")
    assert result.returncode == 69 and "no single bring waits" in result.stderr
    assert not (home / "push-calls").exists()


@pytest.mark.parametrize("need", ["wireguard"])
def test_the_host_admins_needs_are_refused_in_a_persons_account(own_account, need):
    """Prevent a person from believing they gave the host's key or certificates, which only root writes."""
    home = own_account
    result = own_stop(home, need, lines=f"{need} {b64('x')}\n")
    assert result.returncode == 64 and "root" in result.stderr and need in result.stderr
    assert calls(home) == []


@pytest.mark.parametrize(
    "lines, diagnostic",
    [
        (f"vault {b64('p')}\nvault {b64('p')}\n", "second time"),
        ("vault not-base64!\n", "base64"),
        (f"key ../escape {b64('k')}\n", "valid key"),
        (f"wireguard {b64('k')}\n", "not named here"),
        ("", "no line gives vault"),
    ],
)
def test_every_line_is_checked_before_the_vault_is_touched(own_account, lines, diagnostic):
    """Prevent a bad line from leaving the vault half given."""
    home = own_account
    result = own_stop(home, "vault", "keys", lines=lines)
    assert result.returncode == 64 and diagnostic in result.stderr, result.stderr
    assert calls(home) == []


def test_a_refused_passphrase_stops_before_any_key(own_account):
    """Prevent keys from being put into a vault the person could not open."""
    home = own_account
    lines = f"vault {b64('wrong')}\nkey a.key {b64('k')}\n"
    result = own_stop(home, "vault", "keys", lines=lines, extra={"PORELO_STUB_EXIT": "1"})
    assert result.returncode == 65 and "vault unlock" in result.stderr
    assert [call["args"] for call in calls(home)] == [["vault", "unlock", "--passphrase-stdin"]]


def test_identities_without_their_delivery_file_say_what_is_missing(own_account):
    """Prevent a person who was never admitted, or whose tokens were already taken, from seeing success."""
    home = own_account
    result = own_stop(home, "identities")
    assert result.returncode == 69 and "identities.tokens" in result.stderr
    assert calls(home) == []
