"""Guard the SSH key source that enforces each person's VPN restriction."""

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]


def drop_in():
    tasks = yaml.safe_load((ROOT / "roles/porelo/tasks/person.yml").read_text())
    return next(
        task["ansible.builtin.copy"]["content"]
        for task in tasks
        if task.get("ansible.builtin.copy", {}).get("dest") == "/etc/ssh/sshd_config.d/porelo-host-person.conf"
    )


def test_people_cannot_authorize_ssh_keys_outside_the_vpn():
    """Prevent an account-writable authorized_keys file from bypassing the root-owned VPN restrictions."""
    lines = [line.strip().split() for line in drop_in().splitlines() if line.strip()]
    assert lines == [
        ["Match", "Group", "porelo-people"],
        ["AuthorizedKeysFile", "/etc/ssh/authorized_keys/%u"],
        ["Match", "all"],
    ]


def test_sshd_accepts_the_person_drop_in(tmp_path):
    """Prevent an invalid Match configuration from breaking SSH for every account on reload."""
    sshd = shutil.which("sshd")
    if sshd is None:
        pytest.skip("sshd is not installed")
    drop = tmp_path / "person.conf"
    drop.write_text(drop_in())
    key = tmp_path / "host-key"
    made = subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], capture_output=True)
    assert made.returncode == 0, made.stderr
    config = tmp_path / "sshd_config"
    config.write_text(f"HostKey {key}\nAuthorizedKeysFile .ssh/authorized_keys\nInclude {drop}\n")
    result = subprocess.run([sshd, "-t", "-f", str(config)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_ssh_reads_the_drop_in_before_the_play_goes_on():
    """Prevent a later failure in up from leaving the drop-in on disk and a rerun from never reloading SSH."""
    tasks = yaml.safe_load((ROOT / "roles/porelo/tasks/person.yml").read_text())
    index = next(
        number
        for number, task in enumerate(tasks)
        if task.get("ansible.builtin.copy", {}).get("dest") == "/etc/ssh/sshd_config.d/porelo-host-person.conf"
    )
    assert tasks[index + 1].get("ansible.builtin.meta") == "flush_handlers"
