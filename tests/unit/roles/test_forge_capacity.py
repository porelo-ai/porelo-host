"""The forge's capacity check, run by the real ansible-playbook against cpuinfo and meminfo files of a host."""

import os
import subprocess
from pathlib import Path

HERE = Path(__file__).parent


def test_the_defaults_fit_the_server_porelo_rents():
    # The rented server's 16 processors and MemTotal, as its refusal of the old defaults named them.
    done = subprocess.run(
        [
            "ansible-playbook",
            "-i",
            "localhost,",
            str(HERE / "plays" / "capacity.yml"),
            "-e",
            f"__forge_cpuinfo={HERE / 'cpuinfo' / 'sixteen-processors.txt'}",
            "-e",
            f"__forge_meminfo={HERE / 'meminfo' / 'rented-server.txt'}",
        ],
        env=dict(os.environ, ANSIBLE_NOCOLOR="1"),
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stdout + done.stderr
