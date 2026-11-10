"""Prevent pool teardown deleting an unrelated VM or discarding keys before deletion succeeds."""

from pathlib import Path
import re

import jinja2
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]


def test_pool_deletion_precedes_credential_removal_and_follows_the_revert_stop():
    """Do not let the revert race deletion or leave a VM whose keys have been discarded."""
    tasks = yaml.safe_load((ROOT / "roles/vm_pool/tasks/down.yml").read_text())
    stop = next(i for i, t in enumerate(tasks) if "ansible.builtin.systemd_service" in t)
    deletion = next(i for i, t in enumerate(tasks) if "Delete each pool VM" in t["name"])
    cleanup = next(i for i, t in enumerate(tasks) if t.get("ansible.builtin.file", {}).get("state") == "absent")
    assert stop < deletion < cleanup
    assert tasks[deletion].get("failed_when") is not False
    assert tasks[deletion].get("ignore_errors") is not True


@pytest.mark.parametrize(
    "vms,expected",
    [
        ([], []),
        (["unrelated-vm"], []),
        (["unrelated-vm", "porelo-pool-ubuntu-1"], ["porelo-pool-ubuntu-1"]),
    ],
)
def test_only_the_collections_pool_vms_are_deleted(vms, expected):
    """The native delete command must never receive a VM this collection did not make."""
    tasks = yaml.safe_load((ROOT / "roles/vm_pool/tasks/down.yml").read_text())
    deletion = next(t for t in tasks if "Delete each pool VM" in t["name"])
    env = jinja2.Environment(undefined=jinja2.StrictUndefined)
    env.tests["match"] = lambda text, pattern: re.match(pattern, text) is not None
    values = {"__vm_pool_prefix": "porelo-pool", "__vm_pool_listed": {"stdout_lines": vms}}
    values["__vm_pool_named"] = env.from_string(deletion["vars"]["__vm_pool_named"]).render(**values)
    expression = deletion["loop"].strip()[2:-2]
    chosen = env.compile_expression(expression)(**values)
    assert chosen == expected
    for name in chosen:
        argv = [env.from_string(arg).render(item=name) for arg in deletion["ansible.builtin.command"]["argv"]]
        assert argv == [
            "env",
            "-i",
            "PATH=/usr/sbin:/usr/bin:/sbin:/bin",
            "/usr/sbin/porelo-host",
            "pool",
            "delete",
            name,
        ]
