"""Keep Molecule's stand-in for `porelo org` answering the host program, which leads its call with the limits line."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STANDIN = ROOT / "extensions/molecule/default/files/porelo-org-standin.py"
LIMITS = "services=1.0,machines=1.0,polling=1.0,retries=1.0"


def run(*words):
    return subprocess.run([sys.executable, "-I", str(STANDIN), *words], capture_output=True, text=True, check=False)


def test_an_org_call_led_by_the_limits_line_is_answered_by_the_stand_in():
    done = run("--limits", LIMITS, "org", "no-such-verb")
    assert done.returncode == 1, done.stderr
    assert done.stderr.strip() == "the stand-in has no org no-such-verb", done.stderr


def test_an_org_call_without_the_limits_line_is_answered_as_before():
    done = run("org", "no-such-verb")
    assert done.stderr.strip() == "the stand-in has no org no-such-verb", done.stderr


def test_a_limits_line_that_is_missing_its_value_is_refused():
    done = run("--limits")
    assert done.returncode != 0
    assert "--limits needs its line" in done.stderr, done.stderr
