"""Guard the SSH key source and forwarding boundary."""

import grp
import os
import pwd
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]


def ssh_tasks():
    return yaml.safe_load((ROOT / "roles/base/tasks/ssh.yml").read_text())


def drop_in():
    return next(
        task["ansible.builtin.copy"]["content"]
        for task in ssh_tasks()
        if task.get("ansible.builtin.copy", {}).get("dest") == "/etc/ssh/sshd_config.d/10-porelo-host.conf"
    )


def test_every_account_uses_root_owned_keys_and_revocations():
    """Prevent account-writable key files or missing global forwarding restrictions bypassing admission."""
    global_part, people_part = drop_in().split("Match Group porelo-people\n")
    directives = dict(line.split(None, 1) for line in global_part.splitlines())
    assert directives == {
        "Port": "22",
        "PasswordAuthentication": "no",
        "KbdInteractiveAuthentication": "no",
        "AuthorizedKeysFile": "/etc/ssh/authorized_keys/%u",
        "RevokedKeys": "/etc/ssh/porelo-revoked.krl",
        "AllowTcpForwarding": "no",
        "AllowAgentForwarding": "no",
        "X11Forwarding": "no",
        "PermitTunnel": "no",
        "AllowStreamLocalForwarding": "no",
    }
    assert people_part.split() == ["AllowStreamLocalForwarding", "all", "StreamLocalBindUnlink", "yes", "Match", "all"]


def test_sshd_accepts_the_policy_and_only_people_can_forward_sockets(tmp_path):
    """Prevent invalid Match settings breaking logins or allowing nonmembers to forward sockets."""
    sshd = shutil.which("sshd")
    if sshd is None:
        pytest.skip("sshd is not installed")
    key = tmp_path / "host-key"
    made = subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], capture_output=True)
    assert made.returncode == 0, made.stderr
    user = pwd.getpwuid(os.getuid()).pw_name
    group = grp.getgrgid(os.getgid()).gr_name
    config = tmp_path / "sshd_config"
    for match, expected in [(group, "yes"), ("porelo-nonmember-fixture", "no")]:
        config.write_text(f"HostKey {key}\n" + drop_in().replace("Group porelo-people", f"Group {match}"))
        result = subprocess.run(
            [sshd, "-T", "-f", str(config), "-C", f"user={user},host=example.org,addr=192.0.2.1"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        settings = dict(line.split(None, 1) for line in result.stdout.splitlines())
        assert settings["allowstreamlocalforwarding"] == expected
        assert settings["allowtcpforwarding"] == "no"
        assert settings["allowagentforwarding"] == "no"


def test_admin_and_krl_are_seeded_before_the_policy_can_reload():
    """Prevent enabling a key source or KRL that locks out the host admin before the first sync."""
    tasks = ssh_tasks()
    policy = next(
        i
        for i, t in enumerate(tasks)
        if t.get("ansible.builtin.copy", {}).get("dest", "").endswith("10-porelo-host.conf")
    )
    seed = next(
        i
        for i, t in enumerate(tasks)
        if t.get("ansible.builtin.copy", {}).get("dest") == "/etc/ssh/authorized_keys/root"
    )
    krl = next(
        i
        for i, t in enumerate(tasks)
        if t.get("ansible.builtin.shell", {}).get("creates") == "/etc/ssh/porelo-revoked.krl"
    )
    assert seed < policy and krl < policy
    assert tasks[-1].get("ansible.builtin.meta") == "flush_handlers"
