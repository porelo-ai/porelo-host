"""Keep the runner's JDK fetch trying again by the pinned downloads' rule, and only on what waiting may mend."""

import re
from pathlib import Path

import yaml
from jinja2 import Environment, StrictUndefined

ROOT = Path(__file__).resolve().parents[3]
ROLE = ROOT / "roles/forge"
NAME = "runner | Fetch the JDK once and check its pinned digest before unpacking"


def fetch():
    return next(t for t in yaml.safe_load((ROLE / "tasks/runner.yml").read_text()) if t["name"] == NAME)


def tries_again(result):
    """Whether Ansible runs the task again after this result: its until, with Ansible's tests, does not hold."""
    environment = Environment(undefined=StrictUndefined)
    environment.tests["succeeded"] = lambda r: not r.get("failed", False)
    environment.tests["regex"] = lambda value, pattern: re.search(pattern, value) is not None
    variables = yaml.safe_load((ROLE / "vars/main.yml").read_text())
    until = environment.compile_expression(fetch()["until"])
    return not until(
        __forge_runner_jdk_fetch=result,
        __forge_runner_jdk_fetch_unanswered=variables["__forge_runner_jdk_fetch_unanswered"],
    )


def test_the_fetch_waits_the_pinned_rules_fifteen_minutes():
    """Prevent one GitHub outage failing a host's first up, as on 2026-11-08."""
    task = fetch()
    assert task["register"] == "__forge_runner_jdk_fetch"
    assert task["retries"] * task["delay"] <= 15 * 60 < (task["retries"] + 1) * task["delay"]
    assert task["ansible.builtin.get_url"]["timeout"] >= 60


def test_the_fetch_tries_again_on_a_5xx_and_on_no_answer():
    """Prevent a timeout or a 504 of the release download ending the up at once."""
    for result in (
        {"failed": True, "msg": "Connection failure: The read operation timed out"},
        {"failed": True, "msg": "Request failed: <urlopen error [Errno -3] Temporary failure in name resolution>"},
        {"failed": True, "msg": "Incomplete read, (rsp.length=0, cl=10, st.st_size=4) failed to read remaining 6"},
        {"failed": True, "msg": "failed to create temporary content file: The read operation timed out"},
        {"failed": True, "msg": "failed to create temporary content file: timed out"},
        {"failed": True, "msg": "failed to create temporary content file: [Errno 104] Connection reset by peer"},
        {"failed": True, "msg": "failed to create temporary content file: IncompleteRead(4096 bytes read, 10 more)"},
        {"failed": True, "msg": "Request failed", "status_code": 504, "response": "HTTP Error 504: Gateway Timeout"},
        {"failed": True, "msg": "Request failed", "status_code": 502, "response": "HTTP Error 502: Bad Gateway"},
    ):
        assert tries_again(result), result


def test_the_fetch_stops_at_once_on_what_waiting_will_not_mend():
    """Prevent fourteen minutes of waiting for a wrong pin, a missing asset or a refused certificate."""
    for result in (
        {"changed": True, "status_code": 200, "msg": "OK (10 bytes)"},
        {"failed": True, "msg": "Request failed", "status_code": 404, "response": "HTTP Error 404: Not Found"},
        {"failed": True, "msg": "Request failed", "status_code": 403, "response": "HTTP Error 403: Forbidden"},
        {"failed": True, "msg": "The checksum for /tmp/x did not match sha256:aa; it was bb."},
        {
            "failed": True,
            "msg": "Request failed: <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed>",
        },
        {"failed": True, "msg": "Destination /opt/porelo-host is not writable"},
        {"failed": True, "msg": "failed to create temporary content file: [Errno 28] No space left on device"},
        {"failed": True, "msg": "failed to create temporary content file: [Errno 13] Permission denied: '/tmp/x'"},
    ):
        assert not tries_again(result), result
