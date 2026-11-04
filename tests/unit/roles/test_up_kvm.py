"""`up`'s stops on the KVM setting, run by the real ansible-playbook on the playbook itself, before any role."""

import json
import os
import subprocess
from pathlib import Path

PLAYBOOK = Path(__file__).parents[3] / "playbooks" / "up.yml"
SETTINGS = {"porelo_host_inventory_version": 2, "porelo_host_name": "alpha", "porelo_host_network": 7}


def stop(**settings):
    """Runs up with these settings beside the valid ones and returns its exit code and output."""
    done = subprocess.run(
        ["ansible-playbook", "-i", "localhost,", str(PLAYBOOK), "-e", json.dumps(SETTINGS | settings)],
        env=dict(os.environ, ANSIBLE_NOCOLOR="1"),
        capture_output=True,
        text=True,
        check=False,
    )
    return done.returncode, done.stdout + done.stderr


def test_a_pool_on_a_host_that_did_not_ask_for_kvm_stops_before_any_role():
    code, output = stop(porelo_host_vm_pool={"systems": ["ubuntu"], "accounts": 1})
    assert code != 0 and "needs porelo_host_kvm true" in output, output
    assert "Install the host's packages" not in output, output


def test_a_pool_that_said_no_to_kvm_stops_too():
    code, output = stop(porelo_host_kvm=False, porelo_host_vm_pool={"systems": ["ubuntu"], "accounts": 1})
    assert code != 0 and "needs porelo_host_kvm true" in output, output


def test_a_kvm_setting_that_reads_as_words_stops():
    code, output = stop(porelo_host_kvm="no")
    assert code != 0 and "must be true or false" in output, output
    assert "Install the host's packages" not in output, output
