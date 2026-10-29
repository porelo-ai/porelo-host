"""Exercise the person's stop on a terminal without a host account or real credentials."""

import errno
import os
import pty
import select
import signal
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
        (("--stdin", "vault-new"), "root act"),
        (("--stdin", "matrix-token"), "root act"),
        (("--stdin", "wireguard", "wireguard"), "twice"),
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
