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


def test_down_refuses_teardown_while_people_hold_memberships(tmp_path):
    """Prevent tearing down the host while people still hold memberships, or omitting their names and ways back."""
    people = tmp_path / "people"
    people.mkdir(mode=0o700)
    records = {
        "alice": (
            "member=host-admin\nmember=alpha project-admin\nlocked=false\n"
            "ssh=ssh-ed25519 AAAA_PLANTED_ALICE\nexpires=\n"
        ),
        "bob": ("member=beta developer\nlocked=true\n" "ssh=ssh-ed25519 BBBB_PLANTED_BOB\nexpires=\n"),
        "carol": ("member=host-admin\nlocked=false\n" "ssh=ssh-ed25519 CCCC_PLANTED_CAROL\nexpires=\n"),
        "dan": "locked=true\nssh=ssh-ed25519 DDDD_PLANTED_DAN\nexpires=\n",
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
    assert len(failed) == 2, output
    started_tasks = [line["task"] for line in lines if line["state"] == "started"]
    assert not any(
        role in task for task in started_tasks for role in ("matrix", "vm_pool", "forge", "vpn")
    ), f"down must stop nothing while memberships remain: {started_tasks}"
    msg = failed[-1]["msg"]
    assert "alice" in msg and "host-admin" in msg and "alpha project-admin" in msg, msg
    assert "bob" in msg and "beta developer" in msg, msg
    assert "carol" in msg, msg
    assert "dan" not in msg, f"a locked record with zero memberships left must not block down: {msg}"
    assert "Take the project off" in msg and "Purge" in msg, msg
    for secret_like in ("PLANTED_ALICE", "PLANTED_BOB", "PLANTED_CAROL", "PLANTED_DAN"):
        assert secret_like not in output, "card public keys must never be printed by down"


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
            target.write_text("locked=true\nssh=ssh-ed25519 AAAA\nexpires=\n")
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
    locked.write_text("locked=true\nssh=ssh-ed25519 AAAA\nexpires=\n")
    locked.chmod(0o600)
    code, _, output = run_down(tmp_path, empty_memberships)
    assert code == 0, output


def test_a_person_locked_with_a_day_still_stops_down_by_name(tmp_path):
    """Prevent the record the follow writes at a lost membership from reading as malformed to down."""
    people = tmp_path / "people"
    people.mkdir(mode=0o700)
    record = people / "alice.conf"
    record.write_text(
        "member=alpha developer\nlocked=true\nssh=ssh-ed25519 AAAA\nexpires=\nreason=membership\nlocked_on=2026-11-02\n"
    )
    record.chmod(0o600)
    unused_code, unused_lines, text = run_down(tmp_path, people)
    assert "alice (alpha developer)" in text and "malformed" not in text


def test_down_waits_for_the_follow_before_checking_people_and_resumes_on_refusal():
    """Prevent a first follow admitting people after down checked an empty membership directory."""
    from pathlib import Path

    import yaml

    tasks = yaml.safe_load((Path(__file__).resolve().parents[3] / "playbooks/down.yml").read_text())[0]["tasks"]
    pause = next(task for task in tasks if "ansible.builtin.systemd_service" in task)
    check = next(task for task in tasks if "block" in task)
    facts = next(task for task in tasks if "ansible.builtin.stat" in task)
    assert tasks.index(facts) < tasks.index(pause) < tasks.index(check)
    assert facts["ansible.builtin.stat"]["path"] == "/etc/systemd/system/{{ item }}"
    assert facts["loop"] == ["porelo-host-follow.timer", "porelo-host-follow.service"]
    assert facts["register"] == "__porelo_follow_units"
    assert pause["loop"] == "{{ __porelo_follow_units.results }}"
    assert pause["ansible.builtin.systemd_service"] == {"name": "{{ item.item }}", "state": "stopped"}
    assert pause["when"] == "item.stat.exists", "absent units must be harmless"
    assert check["block"][0]["ansible.builtin.include_role"]["tasks_from"] == "people"
    restart, refuse = check["rescue"]
    assert restart["ansible.builtin.systemd_service"] == {"name": "porelo-host-follow.timer", "state": "started"}
    assert restart["when"] == "__porelo_follow_units.results[0].stat.exists"
    assert refuse["ansible.builtin.fail"]["msg"] == "{{ ansible_failed_result.msg }}"
    assert tasks.index(check) < next(
        i for i, task in enumerate(tasks) if task.get("ansible.builtin.include_role", {}).get("tasks_from") == "down"
    )
