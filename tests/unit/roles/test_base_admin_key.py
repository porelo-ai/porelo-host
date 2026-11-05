"""Prevent a person being stopped at root's key file with nothing that says why."""

import json
import os
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).parent
KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILFraP+M35OcLFjqbjgKBCM2EA+3jOGl/hN9CE3dkT7C"
OTHER = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAAgQC7"


def check(tmp_path, content):
    """Run the real tasks over a key file holding the given text."""
    path = tmp_path / "authorized_keys"
    path.write_text(content)
    return path, subprocess.run(
        [
            "ansible-playbook",
            "-i",
            "localhost,",
            str(HERE / "plays/admin_key.yml"),
            "-e",
            json.dumps({"base_host_admin_key_file": str(path)}),
        ],
        env=dict(os.environ, ANSIBLE_NOCOLOR="1"),
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    "content,found",
    [
        (f"{KEY}\n{KEY} second\n", "holds 2 ssh-ed25519 keys and 0 others"),
        ("# nothing but a comment\n", "holds 0 ssh-ed25519 keys and 0 others"),
        (f"{OTHER} one\n", "holds 0 ssh-ed25519 keys and 1 others"),
        (f"{KEY}\n{OTHER} one\n", "holds 1 ssh-ed25519 keys and 1 others"),
    ],
)
def test_a_file_without_exactly_one_ed25519_key_says_so_and_prints_no_key(tmp_path, content, found):
    path, done = check(tmp_path, content)
    assert done.returncode != 0
    assert found in done.stdout, "the person is told what the file holds"
    assert str(path) in done.stdout, "the person is told which file"
    assert "Leave exactly one" in done.stdout, "the person is told what to do"
    assert "AAAA" not in done.stdout + done.stderr


def test_a_line_that_only_looks_like_a_key_says_it_cannot_be_read(tmp_path):
    path, done = check(tmp_path, "ssh-ed25519 notakey\n")
    assert done.returncode != 0
    assert "does not read as a key" in done.stdout and str(path) in done.stdout
    assert "notakey" not in done.stdout + done.stderr


@pytest.mark.parametrize("content", [f"{KEY}\n", f"# the admin\n{KEY} with a comment\n", f"{KEY}\r\n"])
def test_one_ed25519_key_passes(tmp_path, content):
    done = check(tmp_path, content)[1]
    assert done.returncode == 0, done.stdout


@pytest.mark.parametrize(
    "content",
    [
        f"restrict {KEY}\n",
        f"no-port-forwarding,command=\"echo 'Please login'\" {KEY}\n",
        f"{OTHER} ssh-ed25519 admin\n",
    ],
)
def test_a_line_that_does_not_start_with_the_key_is_not_taken_for_one(tmp_path, content):
    """Prevent root locked out: the next task seeds the line's first two words as the key."""
    done = check(tmp_path, content)[1]
    assert done.returncode != 0
    assert "holds 0 ssh-ed25519 keys and 1 others" in done.stdout
    assert "no options before it" in done.stdout
    assert "AAAA" not in done.stdout + done.stderr


def test_nothing_of_ssh_changes_before_the_key_file_is_checked():
    """Prevent a refused file leaving what the check promises it did not touch."""
    import yaml

    root = Path(__file__).resolve().parents[3]
    tasks = yaml.safe_load((root / "roles/base/tasks/ssh.yml").read_text())
    names = [task["name"] for task in tasks]
    check_at = names.index("ssh | Check the pinned host admin key file holds one ed25519 key")
    for task in tasks[:check_at]:
        assert {"ansible.builtin.stat", "ansible.builtin.assert"} & task.keys(), task["name"]


def test_the_seed_takes_a_key_with_a_carriage_return_as_the_key(tmp_path):
    """Prevent a file the check passes being seeded as a key sshd cannot read."""
    root = Path(__file__).resolve().parents[3]
    text = (root / "roles/base/tasks/ssh.yml").read_text()
    seeds = [line.strip() for line in text.splitlines() if "seed=$(awk" in line]
    assert len(seeds) == 1
    path = tmp_path / "authorized_keys"
    path.write_text(f"# the admin\r\n{KEY}\r\n")
    command = seeds[0].replace("{{ base_host_admin_key_file | quote }}", str(path))
    assert command != seeds[0]
    done = subprocess.run(["bash", "-c", f'{command}\nprintf %s "$seed"'], capture_output=True, text=True, check=True)
    assert done.stdout == KEY
