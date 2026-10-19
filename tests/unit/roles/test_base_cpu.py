"""base's CPU check, run by the real ansible-playbook against cpuinfo files in place of /proc/cpuinfo."""

import os
import subprocess
from pathlib import Path

HERE = Path(__file__).parent


def check(cpuinfo):
    """Runs the check on a cpuinfo file and returns its exit code and output."""
    done = subprocess.run(
        [
            "ansible-playbook",
            "-i",
            "localhost,",
            str(HERE / "plays" / "cpu.yml"),
            "-e",
            f"__base_cpuinfo={HERE / 'cpuinfo' / cpuinfo}",
        ],
        env=dict(os.environ, ANSIBLE_NOCOLOR="1"),
        capture_output=True,
        text=True,
        check=False,
    )
    return done.returncode, done.stdout + done.stderr


def test_an_amd_cpu_whose_flags_hold_svm_and_svm_lock_passes():
    # A real AMD flags line, from a Ryzen AI 7 PRO 350: svm_lock beside svm, as on an EPYC 8124P.
    code, output = check("amd-ryzen-svm-lock.txt")
    assert code == 0, output


def test_an_intel_cpu_with_its_vmx_flags_line_passes():
    code, output = check("intel-vmx.txt")
    assert code == 0, output


def test_a_cpu_with_only_a_flag_that_contains_svm_is_refused():
    code, output = check("none-but-svm-lock.txt")
    assert code != 0 and "offers no virtualization" in output, output
