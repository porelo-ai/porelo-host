"""down on a host where up stopped early, run by the real ansible-playbook: it takes down only what is there."""

import os
import subprocess
from pathlib import Path


def test_down_goes_through_when_up_made_neither_the_account_nor_anything_else(tmp_path):
    # As after an up that base's CPU check stopped: no account, no VPN file, no vault.
    inventory = tmp_path / "inventory.yml"
    inventory.write_text("all:\n  hosts:\n    localhost:\n  vars:\n    porelo_host_account: porelo-no-such-account\n")
    done = subprocess.run(
        ["ansible-playbook", "-c", "local", "-i", str(inventory), "porelo.host.down"],
        env=dict(os.environ, ANSIBLE_NOCOLOR="1"),
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stdout + done.stderr
