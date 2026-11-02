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
    global_part, rest = drop_in().split("Match Group porelo-people\n")
    people_part, others_part = rest.split("Match all\n")
    directives = dict(line.split(None, 1) for line in global_part.splitlines())
    # sshd keeps the first value it reads, so neither forwarding keyword may stand before the Match blocks.
    assert directives == {
        "Port": "22",
        "PasswordAuthentication": "no",
        "KbdInteractiveAuthentication": "no",
        "AuthorizedKeysFile": "/etc/ssh/authorized_keys/%u",
        "RevokedKeys": "/etc/ssh/porelo-revoked.krl",
        "AllowAgentForwarding": "no",
        "X11Forwarding": "no",
        "PermitTunnel": "no",
    }
    # OpenSSH opens no Unix socket forward while AllowTcpForwarding is no, and PermitOpen none refuses socket paths
    # too; PermitListen none still refuses every remote TCP listener.
    assert people_part.split() == [
        "AllowTcpForwarding",
        "yes",
        "PermitListen",
        "none",
        "AllowStreamLocalForwarding",
        "all",
        "StreamLocalBindUnlink",
        "yes",
    ]
    assert others_part.split() == ["AllowTcpForwarding", "no", "AllowStreamLocalForwarding", "no"]


def test_sshd_accepts_the_policy_and_only_people_can_forward_sockets(tmp_path):
    """Prevent invalid Match settings breaking logins or allowing nonmembers to forward sockets."""
    sshd = shutil.which("sshd")
    if sshd is None:
        pytest.skip("sshd is not installed")
    key = tmp_path / "host-key"
    made = subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], capture_output=True, check=False
    )
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
            check=False,
        )
        assert result.returncode == 0, result.stderr
        settings = dict(line.split(None, 1) for line in result.stdout.splitlines())
        assert settings["allowstreamlocalforwarding"] == expected
        assert settings["allowtcpforwarding"] == expected
        if expected == "yes":
            assert settings["permitlisten"] == "none"
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
        if "/etc/ssh/authorized_keys/root" in t.get("ansible.builtin.shell", {}).get("cmd", "")
    )
    krl = next(
        i
        for i, t in enumerate(tasks)
        if t.get("ansible.builtin.shell", {}).get("creates") == "/etc/ssh/porelo-revoked.krl"
    )
    assert seed < policy and krl < policy
    assert tasks[-1].get("ansible.builtin.meta") == "flush_handlers"


def seed_root_keys(tmp_path, existing=None, applied=False):
    """Run the role's real seeding step with its paths under a scratch root."""
    tasks = yaml.safe_load((ROOT / "roles/base/tasks/ssh.yml").read_text())
    command = next(
        t["ansible.builtin.shell"]["cmd"]
        for t in tasks
        if "/etc/ssh/authorized_keys/root" in t.get("ansible.builtin.shell", {}).get("cmd", "")
    )
    seed = tmp_path / "seed"
    seed.write_text(f"# the pinned key\n{SEED_KEY} a-comment\n")
    command = command.replace("/etc/", f"{tmp_path}/etc/").replace("{{ base_host_admin_key_file | quote }}", str(seed))
    keys = tmp_path / "etc/ssh/authorized_keys/root"
    keys.parent.mkdir(parents=True)
    if existing is not None:
        keys.write_text(existing)
    if applied:
        marker = tmp_path / "etc/porelo-host/organization/applied.json"
        marker.parent.mkdir(parents=True)
        marker.write_text("{}\n")
    done = subprocess.run(["bash", "-c", command], capture_output=True, text=True, check=True)
    return keys.read_text(), done.stdout, oct(keys.stat().st_mode & 0o777), keys.parent


SEED_KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAISeedSeedSeedSeedSeedSeedSeedSeedSeedSeedSeed"
OTHER_KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOtherOtherOtherOtherOtherOtherOtherOtherOther"


def test_up_seeds_roots_keys_on_a_new_host(tmp_path):
    """Prevent a host whose sshd reads no key for root once the policy is on."""
    text, said, mode, unused = seed_root_keys(tmp_path)
    assert text == f"{SEED_KEY}\n" and said == "changed\n" and mode == "0o644"


def test_up_keeps_the_key_that_reached_root(tmp_path):
    """Prevent `up` locking out the person who runs it with a key other than the seed."""
    text, said, unused, directory = seed_root_keys(tmp_path, f"{OTHER_KEY} a-person\n")
    assert text == f"{OTHER_KEY} a-person\n{SEED_KEY}\n" and said == "changed\n"
    assert [path.name for path in directory.iterdir()] == ["root"]


def test_up_again_changes_nothing(tmp_path):
    """Prevent a repeated `up` growing root's keys or reporting a change."""
    text, said, *unused = seed_root_keys(tmp_path, f"{SEED_KEY} another-comment\n")
    assert text == f"{SEED_KEY} another-comment\n" and said == ""


def test_up_after_a_follow_does_not_bring_a_replaced_admin_back(tmp_path):
    """Prevent the seed giving root back to a host admin the organization replaced."""
    text, said, *unused = seed_root_keys(tmp_path, f"{OTHER_KEY} new-admin\n", applied=True)
    assert text == f"{OTHER_KEY} new-admin\n" and said == ""


def test_up_seeds_a_followed_host_that_lost_roots_keys(tmp_path):
    """Prevent a host locked out for good when root's key file is gone after a follow."""
    text, said, *unused = seed_root_keys(tmp_path, None, applied=True)
    assert text == f"{SEED_KEY}\n" and said == "changed\n"
