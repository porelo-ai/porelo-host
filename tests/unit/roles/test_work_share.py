"""Prevent the share of the host for jobs and the VM pool being fixed at half, or set past the whole host."""

import importlib.machinery
import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "roles/check/files/porelo-host-check"
LIMITS = json.loads((ROOT / "roles/check/files/limits.json").read_text())
HOST = {"host_cpus": 4, "host_kib": 8 * 1024 * 1024}


def load():
    loader = importlib.machinery.SourceFileLoader("porelo_host_check_share", str(SCRIPT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def fit(**request):
    done = subprocess.run(
        ["python3", str(SCRIPT), "--limits", json.dumps(LIMITS), "--fit", json.dumps({**HOST, **request})],
        capture_output=True,
        text=True,
        check=False,
    )
    return json.loads(done.stdout)


@pytest.mark.parametrize("request_", [{}, {"capacity": 2}, {"capacity": 1, "job_cpus": 2, "job_memory": "2g"}])
def test_unset_the_share_is_todays_half(request_):
    assert fit(**request_) == fit(**request_, share_percent=50)
    assert fit(**request_)["share_cpus"] == 2 and fit(**request_)["share_kib"] == 4 * 1024 * 1024


def test_a_larger_share_carries_what_the_half_refuses():
    asked = {"capacity": 3, "job_cpus": 1, "job_memory": "1g"}
    assert fit(**asked)["ok"] is False
    above = fit(**asked, share_percent=75)
    assert above["ok"] is True and above["share_cpus"] == 3 and above["share_kib"] == 6 * 1024 * 1024


@pytest.mark.parametrize("share", [0, 101, 150, "50", True, 50.5, None])
def test_a_share_outside_one_to_a_hundred_is_refused(share):
    answer = fit(capacity=1, share_percent=share)
    assert answer["ok"] is (share is None)


def test_the_check_names_the_setting_and_budgets_the_pool_within_it():
    module = load()
    findings = module.Findings()
    pool = {"systems": ["ubuntu"], "accounts": 1, "memory": 5 * 1024}
    module.check_budgets(findings, LIMITS, {"forge": True, "kvm": True, "pool": pool}, 4, 8 * 1024 * 1024)
    half = {row["id"]: row for row in findings.rows}
    assert half["pool_memory"]["state"] == "fail"
    findings = module.Findings()
    choices = {"forge": True, "kvm": True, "pool": pool, "share_percent": 75}
    module.check_budgets(findings, LIMITS, choices, 4, 8 * 1024 * 1024)
    rows = {row["id"]: row for row in findings.rows}
    assert rows["pool_memory"]["state"] == "pass" and rows["work_share"]["state"] == "pass"
    findings = module.Findings()
    module.check_budgets(findings, LIMITS, {"forge": True, "share_percent": 101}, 4, 8 * 1024 * 1024)
    row = next(row for row in findings.rows if row["id"] == "work_share")
    assert row["state"] == "fail" and "porelo_host_work_share" in row["do"]


def tasks(path):
    """Every task of a file, those in blocks among them."""

    def walk(items):
        for task in items or []:
            yield task
            for key in ("block", "rescue", "always"):
                yield from walk(task.get(key))

    return list(walk(yaml.safe_load((ROOT / path).read_text())))


def test_up_hands_the_setting_to_the_check_and_both_budgets():
    check = tasks("roles/check/tasks/main.yml")[0]
    assert "porelo_host_work_share" in check["vars"]["__check_choices"]["share_percent"]
    capacity = (ROOT / "roles/forge/tasks/capacity.yml").read_text()
    assert 'share_percent: "{{ porelo_host_work_share' in capacity
    assert "porelo_host_work_share" in capacity.split("Stop when the runner's jobs")[1]
    memory = tasks("roles/vm_pool/tasks/memory.yml")
    stop = next(task for task in memory if "Stop when the pool" in task["name"])
    assert "* (porelo_host_work_share | int) // 100" in json.dumps(stop)
    assert "porelo_host_work_share" in stop["ansible.builtin.assert"]["fail_msg"] or "__vm_pool_share" in json.dumps(
        stop["ansible.builtin.assert"]["fail_msg"]
    )


def test_a_share_above_the_half_is_said_in_ups_output():
    notes = [
        task
        for path in ("roles/forge/tasks/capacity.yml", "roles/vm_pool/tasks/memory.yml", "roles/check/tasks/main.yml")
        for task in tasks(path)
        if "porelo_host_note" in (task.get("tags") or [])
    ]
    assert len(notes) == 1
    note = notes[0]
    assert "porelo_host_work_share" in json.dumps(note) and "50" in str(note.get("when"))


def test_the_roles_declare_the_setting():
    for role in ("forge", "vm_pool"):
        specs = (ROOT / f"roles/{role}/meta/argument_specs.yml").read_text()
        assert "porelo_host_work_share" in specs, role


def pool(memory_percent, share=None):
    """vm_pool's memory check on this machine, for one VM of the given percent of its memory."""
    total = int(
        next(line.split()[1] for line in Path("/proc/meminfo").read_text().splitlines() if line.startswith("MemTotal:"))
    )
    variables = {
        "vm_pool_systems": ["ubuntu"],
        "vm_pool_accounts": 1,
        "vm_pool_memory": total * memory_percent // 100 // 1024,
    }
    if share is not None:
        variables["porelo_host_work_share"] = share
    done = subprocess.run(
        [
            "ansible-playbook",
            "-i",
            "localhost,",
            str(ROOT / "tests/unit/roles/plays/pool_memory.yml"),
            "-e",
            json.dumps(variables),
        ],
        env={**os.environ, "ANSIBLE_NOCOLOR": "1"},
        capture_output=True,
        text=True,
        check=False,
    )
    return done.returncode, done.stdout + done.stderr


def test_the_pool_takes_the_share_and_names_it():
    code, output = pool(60)
    assert code != 0 and "exceeds half, porelo_host_work_share unset, of host memory" in output
    code, output = pool(60, 75)
    assert code == 0, output
    code, output = pool(80, 75)
    assert code != 0 and "exceeds 75 percent, porelo_host_work_share, of host memory" in output
