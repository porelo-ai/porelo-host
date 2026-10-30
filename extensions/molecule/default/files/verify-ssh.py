"""Check one Unix socket forward through the installed SSH policy on the test VM."""

import os
from pathlib import Path
import pwd
import shutil
import socket
import subprocess
import tempfile
import threading
import time

USER = "porelo-ssh-fixture"
RUNTIME = Path("/run/porelo-host/people") / USER
KEYS = Path("/etc/ssh/authorized_keys") / USER


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def main():
    if RUNTIME.exists() or KEYS.exists():
        raise RuntimeError("SSH fixture leftovers; refusing to replace them")
    try:
        pwd.getpwnam(USER)
    except KeyError:
        pass
    else:
        raise RuntimeError("SSH fixture account already exists")
    run("useradd", "--create-home", "--shell", "/bin/bash", "--groups", "porelo-people", USER)
    process = None
    listener = socket.socket(socket.AF_UNIX)
    try:
        entry = pwd.getpwnam(USER)
        RUNTIME.mkdir(mode=0o700, parents=True)
        os.chown(RUNTIME, entry.pw_uid, entry.pw_gid)
        service = RUNTIME / "service.sock"
        listener.bind(str(service))
        os.chown(service, entry.pw_uid, entry.pw_gid)
        service.chmod(0o600)
        listener.listen(1)
        listener.settimeout(10)
        errors = []

        def serve():
            try:
                connection, _ = listener.accept()
                with connection:
                    connection.sendall(b"socket forward accepted\n")
            except OSError as error:
                errors.append(type(error).__name__)

        worker = threading.Thread(target=serve)
        with tempfile.TemporaryDirectory(prefix="porelo-ssh-", dir="/root") as directory:
            key = Path(directory) / "key"
            run("ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key))
            KEYS.write_text(key.with_suffix(".pub").read_text())
            KEYS.chmod(0o644)
            forward = Path(directory) / "forward.sock"
            worker.start()
            process = subprocess.Popen(
                ["ssh", "-N", "-i", str(key), "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes",
                 "-o", "StrictHostKeyChecking=accept-new", "-o", f"UserKnownHostsFile={directory}/known_hosts",
                 "-o", "ExitOnForwardFailure=yes", "-L", f"{forward}:{service}", f"{USER}@localhost"],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            deadline = time.monotonic() + 10
            while not forward.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.05)
            with socket.socket(socket.AF_UNIX) as client:
                client.settimeout(5)
                client.connect(str(forward))
                if client.recv(100) != b"socket forward accepted\n":
                    raise RuntimeError("SSH did not forward the person's Unix socket")
            worker.join(timeout=11)
            if errors or worker.is_alive():
                raise RuntimeError("SSH socket fixture failed")
    finally:
        if process is not None:
            process.terminate()
            process.wait(timeout=10)
        listener.close()
        KEYS.unlink(missing_ok=True)
        if RUNTIME.exists():
            shutil.rmtree(RUNTIME)
        ended = subprocess.run(["loginctl", "terminate-user", USER], capture_output=True)
        removed = subprocess.run(["userdel", "--remove", USER], capture_output=True)
        if ended.returncode not in (0, 1) or removed.returncode != 0:
            raise RuntimeError("SSH fixture cleanup failed; inspect the fixture account")


if __name__ == "__main__":
    main()
