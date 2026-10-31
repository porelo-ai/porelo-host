"""Guard root revocation ordering, shared records, expiry ceilings and cleanup failures."""

import json
from contextlib import nullcontext
import runpy
import subprocess
from pathlib import Path

import pytest
import yaml

from test_porelo_host_person import host, sync_host, registry_host, ssh_key, applied
from test_porelo_host_person_cards import cards, sync, registry_card
from test_porelo_host_person_services import services, OWN

ROOT = Path(__file__).resolve().parents[3]


def pending(cards, user="alice", locked=False):
    record = cards.host.records()[user]
    record.update(lock="pending", locked=locked, reason="membership")
    cards.host.record(user, record)
    return record


def test_registry_records_new_revocations_despite_a_stuck_retry(registry_host):
    """Prevent one service outage from keeping a newly revoked key and login authorized."""
    host, state = registry_host
    assert host.invoke("registry", data=b"") == 0
    path = host.path("/etc/porelo-host/people/ada.conf")
    path.write_text(path.read_text() + "lock=pending\n")

    def failed(name, values):
        if name == "forge_lock" and values[0] == "ada":
            raise host.factory.__globals__["Refusal"]("service unavailable", 69)

    host.hook_inspect = failed
    state.registry_reply["commit"] = "b" * 40
    state.registry_reply["persons"][1]["revoked"] = True
    assert host.invoke("registry", data=b"") == 69
    assert applied(host)["commit"] == "b" * 40
    assert "locked=true" in host.path("/etc/porelo-host/people/bo.conf").read_text()
    check = subprocess.run(
        ["ssh-keygen", "-Q", "-f", str(host.path("/etc/ssh/porelo-revoked.krl")), "/dev/stdin"],
        input=state.registry_reply["persons"][1]["ssh"] + "\n",
        text=True,
        capture_output=True,
    )
    assert check.returncode == 1, check.stdout + check.stderr


def test_pending_registry_admin_has_no_authority(registry_host):
    """Prevent an incomplete local lock from retaining registry administration."""
    host, state = registry_host
    assert host.invoke("registry", data=b"") == 0
    path = host.path("/etc/porelo-host/people/ada.conf")
    path.write_text(path.read_text() + "lock=pending\n")
    host.fail = ["gpasswd"]
    state.registry_reply["commit"] = "b" * 40
    assert host.invoke("registry", data=b"", sudo_user="ada") == 65
    assert applied(host)["commit"] == "a" * 40


def test_new_key_revocation_relocks_a_successful_retry_with_porelo(cards):
    """Prevent a prior optional task stop and membership reason from weakening a key revocation."""
    host = cards.host
    pending(cards)
    host.commands.remove("porelo")
    host.write_krl = lambda keys: None
    with pytest.raises(cards.scope["Refusal"]):
        host.apply_registry_cards([cards.reply["persons"][1]], ["alice"], host.records())
    assert host.records()["alice"]["reason"] == "key"
    assert host.records()["alice"]["lock"] == "pending"


@pytest.mark.parametrize("operation", ["sweep", "add"])
def test_later_runs_retry_pending_locks(cards, operation):
    """Prevent the daily sweep or manual admission from leaving unfinished service revocations untouched."""
    host = cards.host
    pending(cards)
    if operation == "sweep":
        host.sweep(host.records())
    else:
        with pytest.raises(cards.scope["Refusal"]):
            host.execute(["add", "alice", "--role", "project-admin"], b"")
    assert ("forge_lock", ("alice",)) in cards.calls
    assert host.records()["alice"].get("lock") is None


def test_sweep_drops_expired_tokens_even_when_pending_lock_retry_fails(cards):
    """Prevent a stopped person's user timer and failed lock from leaving expired task tokens live."""
    host = cards.host
    pending(cards, locked=True)
    host.hooks["forge_lock"] = lambda user: (_ for _ in ()).throw(cards.scope["Refusal"]("offline", 69))
    host.task_records = lambda: [("alice", "task-one", {"valid_before": "2026-01-01T00:00:00Z"})]
    host.forge_configuration = lambda user: ("forge", ["alice", "porelo-alice"])
    host.forge_session = lambda user: nullcontext((None, None, None, None))
    dropped = []
    host.forge_drop_named = lambda *args: dropped.extend(args[-1]) or list(args[-1])
    with pytest.raises(cards.scope["Refusal"]):
        host.sweep(host.records())
    assert dropped == [cards.scope["TASK_TOKEN"] + "task-one"]


@pytest.mark.parametrize("reader", ["project", "down"])
@pytest.mark.parametrize("reason", [None, "membership", "key", "host"])
def test_pending_person_format_is_shared_and_preserved(cards, monkeypatch, reason, reader):
    """Prevent root project removal and teardown from rejecting or discarding unfinished locks."""
    record = pending(cards)
    record["members"] = []
    if reason is None:
        record.pop("reason", None)
    else:
        record["reason"] = reason
    cards.host.record("alice", record)
    project = runpy.run_path(str(ROOT / "roles/forge/files/porelo-host-project"), run_name="format_tests")
    scope = project["read_person"].__globals__
    monkeypatch.setitem(scope, "trusted", lambda *args, **kwargs: None)
    path = cards.host.path("/etc/porelo-host/people/alice.conf")
    if reader == "project":
        members, locked, pending_lock, tail = project["read_person"]("alice", str(path))
        assert pending_lock and not locked
        before = path.read_bytes()
        path.write_text(project["format_person"](members, locked, pending_lock, tail))
        assert path.read_bytes() == before
        assert "lock=pending\n" in path.read_text()
        assert cards.host.records()["alice"]["lock"] == "pending"
    people = path.parent
    for other in people.glob("*.conf"):
        if other != path:
            other.unlink()
    program = yaml.safe_load((ROOT / "roles/porelo/tasks/people.yml").read_text())[0]["ansible.builtin.command"][
        "argv"
    ][-2]
    result = subprocess.run(["python3", "-I", "-c", program, str(people)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == []


@pytest.mark.parametrize("missing_people", [False, True])
def test_deferred_card_entry_bounds_members_and_signers(cards, missing_people):
    """Prevent lagging access from allowing certificates or git signatures beyond the supplied entry."""
    sync(cards)
    host = cards.host
    if missing_people:
        host.path("/etc/porelo-host/projects/alpha.people.json").unlink()
    registry_card(cards, dict(cards.reply["persons"][1], ssh=ssh_key(7)))
    cards.reply["persons"][1]["expires"] = "2026-11-01"
    sync(cards)
    if not missing_people:
        people = json.loads(host.path("/etc/porelo-host/projects/alpha.people.json").read_text())
        assert host.card_expiry(people["alice"]["expires"]) == "20261101000000Z"
    allowed = host.path("/etc/porelo-host/signers/alpha.allowed").read_text().splitlines()
    assert all('valid-before="20261101000000Z"' in line for line in allowed if ssh_key(2) in line)
    assert any(ssh_key(2) in line for line in allowed)


def test_equivalent_expiry_encodings_do_not_defer_new_members(cards):
    """Prevent equivalent timestamps from blocking admission of a verified current card."""
    host = cards.host
    cards.reply["persons"][1]["expires"] = "2026-11-01"
    registry_card(cards, dict(cards.reply["persons"][1], expires="20261101000000Z"))
    sync(cards)
    assert "alpha developer" in host.records()["alice"]["members"]


@pytest.mark.parametrize("operation", ["forge_lock", "forge_drop_tokens"])
def test_forge_revocation_skips_absent_agent_identities(services, operation):
    """Prevent a legacy identity's 404 from blocking revocation or later readmission."""
    recorder = services.recorder
    recorder.users = dict.fromkeys(OWN, False)
    recorder.tokens = {user: [1] for user in OWN}
    config = services.host.forge_configuration("alice")
    base, ca = services.host.forge_endpoint()
    services.host.forge_session = lambda user: nullcontext((config[0], recorder, base, "a" * 40))
    getattr(services.host, operation)("alice")
    assert all(not values for values in recorder.tokens.values())
    assert all(
        not any(identity in path for identity in ("codex-alice", "claude-alice")) for _, path, _ in recorder.requests
    )


def test_cleanup_tolerates_passwd_removal_before_failed_userdel(cards):
    """Prevent a partial userdel failure from replacing the retryable error with a traceback."""
    host = cards.host
    pending(cards)
    host.accounts.pop("alice")
    host.finish_cleanup("alice")
    assert host.records()["alice"]["locked"]


@pytest.mark.parametrize("operation", ["clear_vault", "finish_cleanup"])
@pytest.mark.parametrize("program", ["usermod", "systemctl"])
def test_cleanup_requires_its_privileged_programs(cards, operation, program):
    """Prevent direct cleanup from executing unvalidated privileged binaries."""
    host = cards.host
    pending(cards)
    host.commands.remove(program)
    with pytest.raises(cards.scope["Refusal"], match=program):
        getattr(host, operation)("alice")


@pytest.mark.parametrize(
    "locked, pending_lock, retry_fails", [(True, False, False), (True, True, False), (False, True, True)]
)
def test_revoked_card_preserves_host_lock_reason(cards, locked, pending_lock, retry_fails):
    """Prevent key rotation from reopening an administrative lock after a registry retry."""
    host = cards.host
    record = host.records()["alice"]
    record.update(locked=locked, reason="host")
    if pending_lock:
        record["lock"] = "pending"
    host.record("alice", record)
    if retry_fails:
        host.commands.remove("gpasswd")
    host.write_krl = lambda keys: None
    host.key_revoked = lambda key: True
    try:
        host.apply_registry_cards([cards.reply["persons"][1]], [], host.records())
    except cards.scope["Refusal"]:
        assert retry_fails
    assert host.records()["alice"]["reason"] == "host"


@pytest.mark.parametrize("program", ["runuser", "env", "porelo"])
def test_clear_vault_preflights_before_lifting_expiry(cards, program):
    """Prevent missing cleanup dependencies from lifting expiry on a locked account."""
    host = cards.host
    pending(cards, locked=True)
    host.commands.remove(program)
    before = host.path("/etc/porelo-host/people/alice.conf").read_bytes()
    with pytest.raises(cards.scope["Refusal"], match=program):
        host.clear_vault("alice")
    assert not cards.calls
    assert host.path("/etc/porelo-host/people/alice.conf").read_bytes() == before
