"""Prevent down stopping, or saying nothing, over a firewall systemd cannot tell it about."""

import os
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def down(tmp_path, *extra, systemctl="exit 1\n"):
    """Run the real tasks with a systemctl that answers as given."""
    stub = tmp_path / "systemctl"
    stub.write_text(f"#!/bin/sh\n{systemctl}")
    stub.chmod(0o755)
    return subprocess.run(
        ["ansible-playbook", "-i", "localhost,", str(HERE / "plays/down_firewall.yml"), *extra],
        env=dict(
            os.environ,
            PATH=f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
            ANSIBLE_STDOUT_CALLBACK="porelo.host.lines",
            ANSIBLE_NOCOLOR="1",
        ),
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize("extra", [(), ("--check",)])
def test_a_unit_systemd_cannot_load_does_not_stop_down_and_is_said(tmp_path, extra):
    done = down(tmp_path, *extra)
    assert done.returncode == 0, done.stdout
    assert "it is unknown and unknown" in done.stdout
    assert "systemctl disable --now porelo-host-firewall.service" in done.stdout


def test_the_note_says_the_state_systemd_gives(tmp_path):
    done = down(tmp_path, systemctl='case "$1" in is-active) echo inactive; exit 3;; *) echo disabled; exit 1;; esac\n')
    assert done.returncode == 0, done.stdout
    assert "it is inactive and disabled" in done.stdout
