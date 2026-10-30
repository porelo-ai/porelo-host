"""down's first check on /etc/porelo-host/people, run by the real ansible-playbook with the lines callback."""

import json
import os
import subprocess


def run_down(tmp_path, people_dir):
    """Runs porelo.host.down with the lines callback against a test people directory."""
    inventory = tmp_path / "inventory.yml"
    inventory.write_text(
        "all:\n  hosts:\n    localhost:\n  vars:\n    porelo_host_inventory_version: 2\n"
        "    porelo_host_name: alpha\n    porelo_host_network: 7\n"
    )
    done = subprocess.run(
        [
            "ansible-playbook",
            "-c",
            "local",
            "-i",
            str(inventory),
            "porelo.host.down",
            "-e",
            json.dumps({"__porelo_people_dir": str(people_dir)}),
        ],
        env=dict(os.environ, ANSIBLE_STDOUT_CALLBACK="porelo.host.lines", ANSIBLE_NOCOLOR="1"),
        capture_output=True,
        text=True,
        check=False,
    )
    lines = [json.loads(line) for line in done.stdout.splitlines()]
    return done.returncode, lines, done.stdout + done.stderr


def test_down_refuses_before_stopping_anything_while_people_hold_memberships(tmp_path):
    """Prevent tearing down the host while people still hold memberships, or omitting their names and ways back."""
    people = tmp_path / "people"
    people.mkdir(mode=0o700)
    records = {
        "alice": (
            "member=hand\nmember=alpha project-admin\nlocked=false\n"
            "laptop=laptop ssh-ed25519 AAAA_PLANTED_ALICE wg_PLANTED_ALICE= 10.73.7.3\n"
        ),
        "bob": (
            "member=beta developer\nlocked=true\n"
            "laptop=laptop ssh-ed25519 BBBB_PLANTED_BOB wg_PLANTED_BOB= 10.73.7.4\n"
        ),
        "carol": (
            "role=project-admin\nprojects=\nlocked=false\n"
            "laptop=laptop ssh-ed25519 CCCC_PLANTED_CAROL wg_PLANTED_CAROL= 10.73.7.5\n"
        ),
        "dan": "locked=true\nlaptop=laptop ssh-ed25519 DDDD_PLANTED_DAN wg_PLANTED_DAN= 10.73.7.6\n",
    }
    for user, text in records.items():
        path = people / f"{user}.conf"
        path.write_text(text)
        path.chmod(0o600)

    code, lines, output = run_down(tmp_path, people)
    assert code == 2, output
    plan = next(line for line in lines if line["state"] == "plan")
    assert "people" in plan["steps"][0]["text"].lower(), f"down must check people first in its plan: {plan}"
    failed = [line for line in lines if line["state"] == "failed"]
    assert len(failed) == 1, output
    started_tasks = [line["task"] for line in lines if line["state"] == "started"]
    assert not any(
        role in task for task in started_tasks for role in ("matrix", "vm_pool", "forge", "vpn")
    ), f"down must stop nothing while memberships remain: {started_tasks}"
    msg = failed[0]["msg"]
    assert "alice" in msg and "hand" in msg and "alpha project-admin" in msg, msg
    assert "bob" in msg and "beta developer" in msg, msg
    assert "carol" in msg, msg
    assert "dan" not in msg, f"a locked record with zero memberships left must not block down: {msg}"
    assert "Take the project off" in msg and "Purge" in msg, msg
    for secret_like in ("PLANTED_ALICE", "PLANTED_BOB", "PLANTED_CAROL", "PLANTED_DAN"):
        assert secret_like not in output, "laptop public keys must never be printed by down"


def test_down_fails_closed_on_a_malformed_or_untrusted_people_record(tmp_path):
    """Prevent a corrupt or symlinked person record from being skipped so host teardown proceeds over a person."""
    for kind in ("corrupt", "symlink"):
        case_dir = tmp_path / kind
        case_dir.mkdir()
        people = case_dir / "people"
        people.mkdir(mode=0o700)
        record = people / "alice.conf"
        if kind == "corrupt":
            record.write_text("not-a-valid-record\n")
            record.chmod(0o600)
        else:
            target = case_dir / "outside.conf"
            target.write_text("locked=true\nlaptop=laptop ssh-ed25519 AAAA wg= 10.73.7.3\n")
            target.chmod(0o600)
            record.symlink_to(target)
        code, lines, output = run_down(case_dir, people)
        assert code == 2, f"{kind} must stop down: {output}"
        started_tasks = [line["task"] for line in lines if line["state"] == "started"]
        assert not any(
            role in task for task in started_tasks for role in ("matrix", "vm_pool", "forge", "vpn")
        ), f"{kind} must fail before stopping services: {started_tasks}"


def test_down_goes_through_when_people_directory_is_absent_or_holds_no_memberships(tmp_path):
    """Prevent blocking host teardown when no people directory exists or every membership has already ended."""
    missing = tmp_path / "no-people"
    code, _, output = run_down(tmp_path, missing)
    assert code == 0, output

    empty_memberships = tmp_path / "people"
    empty_memberships.mkdir(mode=0o700)
    locked = empty_memberships / "dan.conf"
    locked.write_text("locked=true\nlaptop=laptop ssh-ed25519 AAAA wg= 10.73.7.6\n")
    locked.chmod(0o600)
    code, _, output = run_down(tmp_path, empty_memberships)
    assert code == 0, output
