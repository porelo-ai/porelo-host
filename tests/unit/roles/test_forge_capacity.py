"""Prevent runner quotas from exhausting a host or refusing a host that can carry bounded jobs."""

import json
import os
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def capacity(tmp_path, processors, memory_mib, explicit=None, expected=None):
    """Run the real tasks twice against invented host measurements and a 256 MiB VM pool."""
    cpuinfo = tmp_path / "cpuinfo"
    cpuinfo.write_text("".join(f"processor : {number}\n" for number in range(processors)))
    meminfo = tmp_path / "meminfo"
    meminfo.write_text(f"MemTotal: {memory_mib * 1024} kB\n")
    variables = {
        "__forge_cpuinfo": str(cpuinfo),
        "__forge_meminfo": str(meminfo),
        "vm_pool_systems": ["fixture-system"],
        "vm_pool_accounts": 1,
        "vm_pool_memory": 256,
        **(explicit or {}),
    }
    if expected is not None:
        variables["expected_capacity"] = expected
    return subprocess.run(
        [
            "ansible-playbook",
            "-i",
            "localhost,",
            str(HERE / "plays/capacity.yml"),
            "-e",
            json.dumps(variables),
        ],
        env=dict(os.environ, ANSIBLE_NOCOLOR="1"),
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    "processors,memory_mib,explicit,expected",
    [
        (4, 8192, {}, [2, 1, "1920m"]),
        (2, 4096, {}, [1, 1, "1792m"]),
        (16, 65536, {}, [2, 4, "8192m"]),
        (32, 131072, {}, [2, 4, "8192m"]),
        (4, 8192, {"forge_runner_capacity": 1}, [1, 2, "3840m"]),
        (4, 8192, {"forge_job_cpus": 2}, [1, 2, "3840m"]),
        (4, 8192, {"forge_job_memory": "3g"}, [1, 2, "3g"]),
    ],
)
def test_unset_bounds_fit_without_changing_explicit_limits(tmp_path, processors, memory_mib, explicit, expected):
    """Prevent small hosts being refused or explicit quotas being silently changed; keep retries stable."""
    done = capacity(tmp_path, processors, memory_mib, explicit, expected)
    assert done.returncode == 0, done.stdout + done.stderr


@pytest.mark.parametrize("processors,memory_mib", [(1, 4096), (2, 1024)])
def test_a_host_below_the_floor_refuses_with_its_measurements(tmp_path, processors, memory_mib):
    """Prevent starting jobs when even the floor exceeds half the host beside the pool."""
    done = capacity(tmp_path, processors, memory_mib)
    output = done.stdout + done.stderr
    assert done.returncode != 0, output
    assert f"{processors} processors and {memory_mib * 1024} KiB total" in output
    assert "cannot carry one job of 1 CPU and 768m beside the VM pool" in output
    refusal = output[output.index("cannot carry one job") : output.index("KiB total")]
    assert "forge_runner_capacity" not in refusal and "forge_job_" not in refusal


@pytest.mark.parametrize(
    "explicit",
    [
        {"forge_runner_capacity": 2, "forge_job_cpus": 4, "forge_job_memory": "8g"},
        {"forge_runner_capacity": 3},
        {"forge_job_cpus": 3},
        {"forge_job_memory": "4g"},
    ],
)
def test_explicit_bounds_that_do_not_fit_are_refused(tmp_path, explicit):
    """Prevent automatic sizing from accepting a host by shrinking a person's explicit bounds."""
    done = capacity(tmp_path, 4, 8192, explicit)
    output = done.stdout + done.stderr
    assert done.returncode != 0, output
    assert "asked for" in output and "lower forge_runner_capacity or the job bounds" in output
    if len(explicit) == 3:
        assert "2 jobs of 4 CPUs and 8g" in output


def test_a_share_above_the_half_carries_more_jobs_and_says_so(tmp_path):
    """Prevent the half refusing what an operator chose to give the jobs, or the choice passing unsaid."""
    done = capacity(tmp_path, 4, 8192, {"porelo_host_work_share": 75, "forge_runner_capacity": 3}, [3, 1, "1962m"])
    output = done.stdout + done.stderr
    assert done.returncode == 0, output
    assert "porelo_host_work_share is 75 percent" in output and "keep 25 percent" in output


def test_unset_the_share_is_named_in_the_refusal_and_nothing_is_said_above_it(tmp_path):
    """Prevent a person meeting the half without learning it can be set."""
    done = capacity(tmp_path, 4, 8192, {"forge_runner_capacity": 3})
    output = done.stdout + done.stderr
    assert done.returncode != 0, output
    assert "within half the host, porelo_host_work_share unset: 2 of 4 processors" in output
    assert "or raise porelo_host_work_share" in output and "percent: the forge's jobs" not in output


def test_a_set_share_is_named_with_its_parts_in_the_refusal(tmp_path):
    """Prevent a refusal under a raised share still speaking of the half."""
    done = capacity(tmp_path, 4, 8192, {"porelo_host_work_share": 75, "forge_runner_capacity": 4})
    output = done.stdout + done.stderr
    assert done.returncode != 0, output
    assert "within 75 percent of the host, porelo_host_work_share: 3 of 4 processors" in output
