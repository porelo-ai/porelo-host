"""down on a host where up stopped early, run by the real ansible-playbook: it takes down only what is there."""

import os
import subprocess
from pathlib import Path


def test_down_goes_through_when_up_made_nothing(tmp_path):
    # As after an up that base's CPU check stopped: no account of the forge or the homeserver, no VPN file.
    inventory = tmp_path / "inventory.yml"
    inventory.write_text(
        "all:\n  hosts:\n    localhost:\n  vars:\n    porelo_host_inventory_version: 2\n"
        "    porelo_host_name: alpha\n    porelo_host_network: 7\n"
    )
    done = subprocess.run(
        ["ansible-playbook", "-c", "local", "-i", str(inventory), "porelo.host.down"],
        env=dict(os.environ, ANSIBLE_NOCOLOR="1"),
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stdout + done.stderr
