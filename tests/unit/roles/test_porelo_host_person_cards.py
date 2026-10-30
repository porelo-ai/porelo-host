"""Prevent card reconciliation from leaking project authority or reviving purged accounts."""

import datetime
import json
import os
import runpy
import stat
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_porelo_host_person import ssh_key

SCRIPT = Path(__file__).resolve().parents[3] / "roles/porelo/files/porelo-host-person"


@pytest.fixture
def cards(tmp_path, monkeypatch):
    scope = runpy.run_path(str(SCRIPT), run_name="card_tests")
    host = scope["Host"]()
    host.root, host.owner, host.group = tmp_path, os.getuid(), os.getgid()
    host.euid = 0
    host.accounts = {"ada": 1000, "alice": 1001, "bo": 1002}
    host.groups = {"porelo-people"}
    host.now = lambda: datetime.datetime(2026, 10, 30, tzinfo=datetime.timezone.utc)
    calls = []
    host.runner = lambda args, input=None: (calls.append((args, input)) or subprocess.CompletedProcess(args, 0, "", ""))
    host.commands = {"gpasswd", "usermod", "loginctl", "systemctl", "runuser", "porelo", "systemd-run"}
    monkeypatch.setattr(
        scope["pwd"],
        "getpwnam",
        lambda user: SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid(), pw_dir=str(tmp_path / "home" / user)),
    )
    for name in host.hooks:
        host.hooks[name] = lambda *args, name=name: calls.append((name, args))
    host.write(host.path("/etc/porelo-host/forge.conf"), "host=host\n", 0o600)
    host.write(host.path("/etc/login.defs"), "UID_MIN 1000\n", 0o644)
    host.write(host.path("/etc/subuid"), "", 0o644)
    host.write(host.path("/etc/subgid"), "", 0o644)
    persons = [person("ada", 1, role="project-admin"), person("alice", 2), person("bo", 3)]
    host.write(
        host.path("/etc/porelo-host/registry/applied.json"),
        json.dumps(
            {
                "commit": "a" * 40,
                "projects": [{"name": "alpha", "admin": "ada"}],
                "persons": persons,
                "revoked": [],
            }
        ),
        0o600,
    )
    records = [("ada", 1, ["hand"]), ("alice", 2, ["beta developer"]), ("bo", 3, ["beta developer"])]
    for user, number, members in records:
        host.write(
            host.path(f"/etc/porelo-host/people/{user}.conf"),
            "".join(f"member={member}\n" for member in members) + f"locked=false\nssh={ssh_key(number)}\nexpires=\n",
            0o600,
        )
    host.write(
        host.path("/etc/porelo-host/projects/alpha.conf"),
        f"admin=ada\nsigned_by={ssh_key(9)}\npublisher=porelo-publisher-alpha\n",
        0o600,
    )
    reply = {"persons": [persons[0], persons[1]], "admins": ["ada"]}
    host.verify_bundles = lambda *args: (reply, "1" * 40, "2" * 40, [ssh_key(9)])
    host.forge_project_apply = lambda project, admin, desired: calls.append(("teams", (project, desired)))
    host.matrix_members = lambda project, desired: calls.append(("rooms", (project, desired)))
    host.key_revoked = lambda key: False
    return SimpleNamespace(host=host, calls=calls, reply=reply, scope=scope)


def person(login, number, role="developer", **values):
    return {
        "login": login,
        "ssh": ssh_key(number),
        "expires": None,
        "revoked": False,
        "role": role,
        "hosts": ["host"],
        "locked": False,
        **values,
    }


def registry_card(cards, entry):
    path = cards.host.path("/etc/porelo-host/registry/applied.json")
    registry = json.loads(path.read_text())
    registry["persons"] = [item for item in registry["persons"] if item["login"] != entry["login"]]
    registry["persons"].append({key: entry[key] for key in ("login", "ssh", "expires", "revoked")})
    path.write_text(json.dumps(registry))


def sync(cards):
    host = cards.host
    return host.sync("alpha", host.records(), host.accounts)


def test_project_lock_removes_only_its_authority_and_let_back_in_restores_it(cards):
    """Prevent a project admin from ending another project's sessions or retaining its own signers."""
    sync(cards)
    cards.calls.clear()
    cards.reply["persons"][1]["locked"] = True
    sync(cards)
    record = cards.host.records()["alice"]
    assert record["members"] == ["beta developer"] and not record["locked"]
    assert not any(call[0] in ("forge_lock", "matrix_expel_revoke") for call in cards.calls)
    assert not any(isinstance(call[0], list) and "terminate-user" in call[0] for call in cards.calls)
    assert ("rooms", ("alpha", ["ada"])) in cards.calls
    assert "alice" not in cards.host.read(cards.host.path("/etc/porelo-host/signers/alpha.allowed"))
    cards.reply["persons"][1]["locked"] = False
    sync(cards)
    assert "alpha developer" in cards.host.records()["alice"]["members"]
    assert ("rooms", ("alpha", ["ada", "alice"])) in cards.calls


def test_signers_are_project_local_and_rotation_preserves_only_history(cards):
    """Prevent cross-project signing and unrestricted task CA signatures after key replacement."""
    sync(cards)
    path = cards.host.path("/etc/porelo-host/signers/alpha.allowed")
    text = path.read_text()
    assert "alice " in text and "bo " not in text and ssh_key(9) not in text
    assert 'task:* cert-authority,namespaces="git"' in text
    assert stat.S_IMODE(path.stat().st_mode) == 0o644
    cards.reply["persons"][1]["ssh"] = ssh_key(4)
    registry_card(cards, cards.reply["persons"][1])
    sync(cards)
    lines = path.read_text().splitlines()
    assert any(ssh_key(2) in line and "valid-before=" in line for line in lines)
    assert all("valid-before=" in line for line in lines if ssh_key(2) in line)


@pytest.mark.parametrize("reason", ["host", "current-key", "last-membership"])
def test_host_loss_ends_sessions_and_revokes_tokens(cards, reason):
    """Prevent existing tunnels or forge credentials from surviving host-wide removal."""
    sync(cards)
    record = cards.host.records()["alice"]
    if reason == "last-membership":
        record["members"] = ["alpha developer"]
        cards.host.record("alice", record)
        cards.reply["persons"] = cards.reply["persons"][:1]
        sync(cards)
    elif reason == "current-key":
        cards.host.key_revoked = lambda key: key == ssh_key(2)
        sync(cards)
    else:
        cards.host.execute(["lock", "alice"], None)
    assert cards.host.records()["alice"]["locked"]
    assert ("forge_lock", ("alice",)) in cards.calls
    assert any(isinstance(call[0], list) and call[0][:2] == ["loginctl", "terminate-user"] for call in cards.calls)


def test_an_old_revoked_key_does_not_lock_the_current_person(cards):
    """Prevent a replaced historical key in the KRL from blocking the current card."""
    cards.host.key_revoked = lambda key: key == ssh_key(8)
    sync(cards)
    assert not cards.host.records()["alice"]["locked"]
    assert not any(call[0] == "forge_lock" for call in cards.calls)


def test_purged_login_is_refused_without_blocking_another_lock(cards):
    """Prevent identity reuse while keeping other revocations effective in the same intake."""
    cards.host.write(cards.host.path("/etc/porelo-host/people/purged"), "alice\n", 0o600)
    cards.reply["persons"][0]["locked"] = True
    answer = sync(cards)
    assert any("alice" in item for item in answer["refused"])
    assert "alpha developer" not in cards.host.records()["alice"]["members"]


def test_card_expiry_replaces_authorized_key_and_records_have_no_laptops(cards):
    """Prevent stale device credentials from surviving card reconciliation."""
    cards.reply["persons"][1]["expires"] = "2027-01-02"
    registry_card(cards, cards.reply["persons"][1])
    sync(cards)
    path = cards.host.path("/etc/ssh/authorized_keys/alice")
    assert path.read_text() == f'expiry-time="20270102000000Z" {ssh_key(2)}\n'
    assert "laptop=" not in cards.host.path("/etc/porelo-host/people/alice.conf").read_text()
    with pytest.raises(cards.scope["Refusal"]):
        cards.host.execute(["add", "new", "--role", "project-admin"], b"l1 obsolete device input\n")


def test_purge_records_a_permanent_private_tombstone(cards):
    """Prevent a removed Linux account from being silently recreated under the same login."""
    host = cards.host
    record = host.records()["alice"]
    host.purge("alice", record, False, True)
    path = host.path("/etc/porelo-host/people/purged")
    assert path.read_text() == "alice\n"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert "alice" not in host.records()
    host.accounts.pop("alice")
    with pytest.raises(cards.scope["Refusal"], match="purged"):
        host.execute(["add", "alice", "--role", "project-admin"], b"")


def test_host_lock_removes_signers_and_rooms_from_all_projects(cards):
    """Prevent a host-wide lock from leaving signatures or room membership active until a project sync."""
    sync(cards)
    cards.host.project_signers("beta", {"alice": person("alice", 2), "bo": person("bo", 3)})
    cards.host.write(
        cards.host.path("/etc/porelo-host/projects/beta.conf"),
        f"admin=bo\nsigned_by={ssh_key(9)}\npublisher=porelo-publisher-beta\n",
        0o600,
    )
    cards.host.write(
        cards.host.path("/etc/porelo-host/projects/beta.people.json"),
        json.dumps({"alice": person("alice", 2), "bo": person("bo", 3)}),
        0o600,
    )
    cards.host.execute(["lock", "alice"], None)
    for project in ("alpha", "beta"):
        assert "alice" not in cards.host.path(f"/etc/porelo-host/signers/{project}.allowed").read_text()
    assert ("rooms", ("beta", ["bo"])) in cards.calls
    assert any(call[0] == ["gpasswd", "--delete", "alice", "porelo-people"] for call in cards.calls)
    cards.calls.clear()
    sync(cards)
    assert cards.host.records()["alice"]["locked"], "project sync must not undo a host lock"


def test_missing_admins_means_no_room_administrators(cards):
    """Prevent a missing authorization field from retaining an older admin's room authority."""
    sync(cards)
    cards.reply.pop("admins")
    sync(cards)
    assert cards.host.path("/etc/porelo-host/matrix/alpha.admins").read_text() == ""


@pytest.mark.parametrize("login", ["porelo", "porelo-alice", "Alice", "../alice"])
def test_reserved_or_unsafe_logins_are_never_admitted(cards, login):
    """Prevent verify answers from taking over service accounts or escaping root's paths."""
    cards.reply["persons"].append(person(login, 5))
    with pytest.raises(cards.scope["Refusal"]):
        sync(cards)


def test_device_records_are_refused(cards):
    """Prevent old per-device authorization from surviving as an alternate source of keys."""
    path = cards.host.path("/etc/porelo-host/people/alice.conf")
    path.write_text(f"member=hand\nlocked=false\nlaptop=l1 {ssh_key(2)} unused 192.0.2.5\n")
    with pytest.raises(cards.scope["Refusal"]):
        cards.host.records()


def test_expired_or_revoked_project_card_loses_only_its_project(cards):
    """Prevent expired project access from retaining teams without letting it lock another project."""
    for change in ({"expires": "2000-01-01"}, {"revoked": True}):
        cards.reply["persons"][1] = person("alice", 2)
        registry_card(cards, cards.reply["persons"][1])
        sync(cards)
        cards.reply["persons"][1].update(change)
        if "expires" in change:
            registry_card(cards, cards.reply["persons"][1])
        sync(cards)
        assert cards.host.records()["alice"]["members"] == ["beta developer"]
        assert not cards.host.records()["alice"]["locked"]


def test_signer_directory_is_readable_by_the_forge(cards):
    """Prevent root's signer publication from being unreachable to the forge account."""
    sync(cards)
    directory = cards.host.path("/etc/porelo-host/signers")
    assert stat.S_IMODE(directory.stat().st_mode) == 0o755


def test_down_reader_accepts_card_records_and_the_purged_list(cards):
    """Prevent the teardown guard from rejecting the new record contract or omitting remaining memberships."""
    import yaml

    role = SCRIPT.parents[1] / "tasks/people.yml"
    program = yaml.safe_load(role.read_text())[0]["ansible.builtin.command"]["argv"][-2]
    people = cards.host.path("/etc/porelo-host/people")
    cards.host.write(people / "purged", "old-login\n", 0o600)
    answer = subprocess.run(
        ["/usr/bin/python3", "-I", "-c", program, str(people)], text=True, capture_output=True, check=False
    )
    assert answer.returncode == 0, answer.stderr
    assert json.loads(answer.stdout) == ["ada (hand)", "alice (beta developer)", "bo (beta developer)"]


def test_people_group_drops_unrecorded_and_locked_logins(cards, monkeypatch):
    """Prevent stale supplementary membership from granting socket forwarding or sudo to an unadmitted account."""
    monkeypatch.setattr(
        cards.scope["grp"], "getgrnam", lambda name: SimpleNamespace(gr_mem=["ada", "alice", "bo", "outsider"])
    )
    sync(cards)
    assert (["gpasswd", "--delete", "outsider", "porelo-people"], None) in cards.calls


def test_real_krl_query_distinguishes_current_and_historical_keys(cards):
    """Prevent a KRL parser assumption from revoking the wrong current identity."""
    host = cards.host
    host.commands.add("ssh-keygen")
    host.runner = lambda args, input=None: subprocess.run(
        args, input=input, text=True, capture_output=True, check=False
    )
    host.key_revoked = cards.scope["Host"].key_revoked.__get__(host)
    host.write_krl([ssh_key(8)])
    assert host.key_revoked(ssh_key(8))
    assert not host.key_revoked(ssh_key(2))
    host.path("/etc/ssh/porelo-revoked.krl").write_bytes(b"broken KRL")
    with pytest.raises(cards.scope["Refusal"]):
        host.key_revoked(ssh_key(2))


def test_failed_service_lock_cannot_be_undone_by_project_sync(cards):
    """Prevent a failed external revocation from leaving a host lock writable by a project admin."""
    sync(cards)

    def unavailable(user):
        raise cards.scope["Refusal"]("fixture service unavailable", 69)

    cards.host.hooks["forge_lock"] = unavailable
    with pytest.raises(cards.scope["Refusal"]):
        cards.host.execute(["lock", "alice"], None)
    cards.host.hooks["forge_lock"] = lambda user: None
    sync(cards)
    assert cards.host.records()["alice"]["locked"]
    assert not cards.host.path("/etc/ssh/authorized_keys/alice").exists()


def test_rotated_history_never_extends_the_previous_cards_expiry(cards):
    """Prevent replacement from extending the period in which an expired old key can sign."""
    cards.reply["persons"][1]["expires"] = "2026-11-01"
    registry_card(cards, cards.reply["persons"][1])
    sync(cards)
    cards.host.now = lambda: datetime.datetime(2026, 11, 2, tzinfo=datetime.timezone.utc)
    cards.reply["persons"][1] = person("alice", 4)
    registry_card(cards, cards.reply["persons"][1])
    sync(cards)
    text = cards.host.path("/etc/porelo-host/signers/alpha.allowed").read_text()
    old = [line for line in text.splitlines() if ssh_key(2) in line]
    assert len(old) == 2
    assert all('valid-before="20261101000000Z"' in line for line in old)


def test_key_revocation_does_not_weaken_an_existing_host_lock(cards):
    """Prevent clearing a revoked key from undoing a separate host administrator lock."""
    sync(cards)
    cards.host.execute(["lock", "alice"], None)
    cards.host.key_revoked = lambda key: key == ssh_key(2)
    sync(cards)
    cards.host.key_revoked = lambda key: False
    sync(cards)
    assert cards.host.records()["alice"]["locked"]


def test_a_key_cannot_be_shared_with_a_person_of_another_project(cards):
    """Prevent a card from authenticating as an unrelated already admitted login."""
    cards.reply["persons"].append(person("eve", 3))
    answer = sync(cards)
    assert any("eve" in reason for reason in answer["refused"])
    assert "eve" not in cards.host.records()


def test_installed_add_refuses_device_input_instead_of_ignoring_it(cards, monkeypatch):
    """Prevent the installed CLI from retaining an alternate device-input admission path."""
    import io

    monkeypatch.setattr(cards.scope["sys"], "stdin", io.TextIOWrapper(io.BytesIO(b"l1 old device input\n")))
    with pytest.raises(cards.scope["Refusal"], match="no credential input"):
        cards.host.execute(["add", "ada", "--role", "project-admin"], None)


@pytest.mark.parametrize("change", ["absent", "key", "expiry", "revoked", "project-revoked", "old-revoked-key"])
def test_sync_refuses_cards_outside_the_applied_registry_and_applies_the_rest(cards, change):
    """Prevent project bundles from creating host identities or replacing host-wide credentials."""
    host = cards.host
    entry = cards.reply["persons"][1]
    if change == "absent":
        path = host.path("/etc/porelo-host/registry/applied.json")
        registry = json.loads(path.read_text())
        registry["persons"] = [item for item in registry["persons"] if item["login"] != "alice"]
        path.write_text(json.dumps(registry))
    elif change in ("key", "old-revoked-key"):
        entry["ssh"] = ssh_key(7)
        if change == "old-revoked-key":
            host.key_revoked = lambda key: key == ssh_key(7)
    elif change == "expiry":
        entry["expires"] = "2027-01-01"
    elif change == "project-revoked":
        entry["revoked"] = True
    else:
        path = host.path("/etc/porelo-host/registry/applied.json")
        registry = json.loads(path.read_text())
        registry["persons"][1]["revoked"] = True
        path.write_text(json.dumps(registry))
    answer = sync(cards)
    assert any(entry["login"] in reason for reason in answer["refused"])
    assert "alpha project-admin" in host.records()["ada"]["members"]
    assert entry["login"] not in json.loads(host.path("/etc/porelo-host/projects/alpha.people.json").read_text())
    assert host.records()["alice"]["ssh"] == ssh_key(2)
    assert host.records()["alice"]["expires"] is None


def test_krl_updates_keep_all_previously_revoked_keys(cards):
    """Prevent registry refresh or key rotation from reviving an already revoked key."""
    host = cards.host
    host.commands.add("ssh-keygen")
    host.runner = lambda args, input=None: subprocess.run(args, input=input, text=True, capture_output=True)
    host.key_revoked = cards.scope["Host"].key_revoked.__get__(host)
    host.write_krl([ssh_key(8)])
    host.write_krl([ssh_key(7)])
    host.write_krl([])
    assert host.key_revoked(ssh_key(8))
    assert host.key_revoked(ssh_key(7))
    assert not host.key_revoked(ssh_key(2))


def test_lock_skips_membership_files_of_unregistered_projects(cards):
    """Prevent orphaned project state from permanently blocking host lock and purge."""
    sync(cards)
    cards.host.path("/etc/porelo-host/projects/alpha.conf").unlink()
    cards.host.execute(["lock", "alice"], None)
    assert cards.host.records()["alice"]["locked"]
    cards.host.accounts.pop("alice")
    cards.host.execute(["purge", "alice"], None)
    assert "alice" not in cards.host.records()


@pytest.mark.parametrize("failed", [None, "forge", "rooms"])
def test_lock_preserves_verified_admins_and_attempts_each_service(cards, failed):
    """Prevent role escalation and one service failure from retaining another service's authority."""
    cards.reply["persons"][1]["role"] = "project-admin"
    cards.reply["admins"] = ["alice"]
    sync(cards)
    attempts = []

    def service(name):
        def apply(*args):
            attempts.append(name)
            if name == failed:
                raise cards.scope["Refusal"](f"{name} unavailable", 69)

        return apply

    cards.host.forge_project_apply = service("forge")
    cards.host.matrix_members = service("rooms")
    if failed:
        with pytest.raises(cards.scope["Refusal"], match=f"{failed} unavailable"):
            cards.host.execute(["lock", "alice"], None)
    else:
        cards.host.execute(["lock", "alice"], None)
    assert attempts == ["forge", "rooms"]
    assert cards.host.path("/etc/porelo-host/matrix/alpha.admins").read_text() == ""


def test_sync_updates_admins_even_when_other_services_fail(cards):
    """Prevent a Forgejo failure from retaining revoked Matrix room administration."""
    sync(cards)
    cards.reply["admins"] = []

    def unavailable(*args):
        raise cards.scope["Refusal"]("forge unavailable", 69)

    cards.host.forge_project_apply = unavailable
    with pytest.raises(cards.scope["Refusal"]):
        sync(cards)
    assert cards.host.path("/etc/porelo-host/matrix/alpha.admins").read_text() == ""


@pytest.mark.parametrize("target", ["admins", "matrix-directory", "authorized", "people", "allowed"])
def test_root_publications_and_lock_refuse_symlinks(cards, target, tmp_path):
    """Prevent root publication or revocation from following or removing an untrusted link."""
    host = cards.host
    sync(cards)
    paths = {
        "admins": "/etc/porelo-host/matrix/alpha.admins",
        "matrix-directory": "/etc/porelo-host/matrix",
        "authorized": "/etc/ssh/authorized_keys/alice",
        "people": "/etc/porelo-host/projects/alpha.people.json",
        "allowed": "/etc/porelo-host/signers/alpha.allowed",
    }
    path = host.path(paths[target])
    outside = tmp_path / "outside"
    if target == "matrix-directory":
        path.rename(outside)
        outside.chmod(0o700)
    else:
        path.unlink()
    path.symlink_to(outside)
    with pytest.raises(cards.scope["Refusal"]):
        if target == "authorized":
            host.lock("alice", host.records()["alice"], False)
        else:
            sync(cards)
    assert path.is_symlink()
    if target == "matrix-directory":
        assert stat.S_IMODE(outside.stat().st_mode) == 0o700


@pytest.mark.parametrize("verb", ["lock", "purge"])
def test_locked_record_without_linux_account_can_be_locked_or_purged(cards, verb):
    """Prevent a missing Linux account from crashing recovery of a recorded lock."""
    host = cards.host
    record = host.records()["alice"]
    record["locked"] = True
    host.record("alice", record)
    host.accounts.pop("alice")
    authorized = host.path("/etc/ssh/authorized_keys/alice")
    host.write(authorized, ssh_key(2) + "\n", 0o644)
    host.execute([verb, "alice"], None)
    assert not authorized.exists()
    assert (verb == "purge") == ("alice" not in host.records())
    assert not any(isinstance(args, list) and args[0] == "usermod" for args, _ in cards.calls)


def test_revoked_login_with_a_refused_card_still_locks_its_recorded_key(cards):
    """Prevent a malformed revocation from leaving a recorded account or key active."""
    host = cards.host
    refused = []
    persons, revoked = host.registry_persons([person("alice", 2, ssh="invalid", revoked=True)], None, refused)
    keys = []
    host.write_krl = lambda values: keys.extend(values)
    host.apply_registry_cards(persons, revoked, host.records())
    assert refused
    assert host.records()["alice"]["locked"]
    assert ssh_key(2) in keys


def test_purged_revocation_still_enters_the_krl(cards):
    """Prevent a purged person's newly supplied revoked key from remaining usable elsewhere."""
    host = cards.host
    host.write(host.path("/etc/porelo-host/people/purged"), "carol\n", 0o600)
    persons, revoked = host.registry_persons([person("carol", 7, revoked=True)], None, [])
    keys = []
    host.write_krl = lambda values: keys.extend(values)
    host.apply_registry_cards(persons, revoked, host.records())
    assert ssh_key(7) in keys


@pytest.mark.parametrize("other", ["entry", "record"])
def test_registry_refuses_keys_owned_by_another_login(cards, other):
    """Prevent shared credentials from granting access as a different person."""
    entries = [person("carol", 7), person("dan", 7)] if other == "entry" else [person("carol", 2)]
    refused = []
    persons, _ = cards.host.registry_persons(entries, None, refused)
    assert refused
    assert len(persons) == (1 if other == "entry" else 0)


def test_project_revocation_reports_all_service_failures(cards):
    """Prevent an earlier dependency failure from hiding failed revocations in other services."""
    sync(cards)
    attempts = []

    def failure(name):
        def apply(*args):
            attempts.append(name)
            raise cards.scope["Refusal"](name + " unavailable", 69)

        return apply

    cards.host.forge_project_apply = failure("forge")
    cards.host.matrix_members = failure("rooms")
    cards.host.matrix_admins = failure("admins")
    with pytest.raises(cards.scope["Refusal"]) as error:
        cards.host.revoke_project_access("alice")
    assert attempts == ["forge", "rooms", "admins"]
    assert all(name + " unavailable" in str(error.value) for name in attempts)


def test_sync_does_not_restore_a_locked_person_without_an_account(cards):
    """Prevent a stale record from causing Linux commands or runtime admission for a missing account."""
    host = cards.host
    record = host.records()["alice"]
    record.update(locked=True, reason="membership")
    host.record("alice", record)
    host.accounts.pop("alice")
    sync(cards)
    assert host.records()["alice"]["locked"]
    assert not any(isinstance(args, list) and args[0] == "usermod" and args[-1] == "alice" for args, _ in cards.calls)


def test_lock_removes_local_and_forge_access_before_project_cleanup(cards):
    """Prevent slow project dependencies from prolonging gate access or Forgejo token validity."""
    sync(cards)
    cards.calls.clear()
    cards.host.execute(["lock", "alice"], None)
    teams = next(index for index, call in enumerate(cards.calls) if call[0] == "teams")
    gate = next(
        index for index, call in enumerate(cards.calls) if call[0] == ["gpasswd", "--delete", "alice", "porelo-people"]
    )
    forge = next(index for index, call in enumerate(cards.calls) if call[0] == "forge_lock")
    assert gate < teams and forge < teams


def test_malformed_membership_cards_refuse_without_crashing(cards):
    """Prevent corrupt project state from crashing host revocation with an uncaught exception."""
    sync(cards)
    cards.host.path("/etc/porelo-host/projects/alpha.people.json").write_text('{"alice": {}, "ada": null}')
    with pytest.raises(cards.scope["Refusal"], match="malformed"):
        cards.host.revoke_project_access("alice")


@pytest.mark.parametrize("verb", ["lock", "purge"])
def test_missing_passwd_account_does_not_crash_locked_record_recovery(cards, monkeypatch, verb):
    """Prevent production passwd lookup from crashing recovery when no injected account map exists."""
    host = cards.host
    record = host.records()["alice"]
    record["locked"] = True
    host.record("alice", record)
    host.accounts = None
    authorized = host.path("/etc/ssh/authorized_keys/alice")
    host.write(authorized, ssh_key(2) + "\n", 0o644)
    lookup = cards.scope["pwd"].getpwnam

    def passwd(user):
        if user == "alice":
            raise KeyError(user)
        return lookup(user)

    monkeypatch.setattr(cards.scope["pwd"], "getpwnam", passwd)
    if verb == "lock":
        host.lock("alice", record, True)
    else:
        host.purge("alice", record, True, False)
    assert not authorized.exists()
    assert not any(
        isinstance(args, list) and args[0] in ("usermod", "loginctl", "systemctl", "runuser") for args, _ in cards.calls
    )


@pytest.mark.parametrize("verb", ["lock", "purge"])
@pytest.mark.parametrize("locked", [False, True])
def test_missing_account_with_runtime_still_allows_revocation(cards, monkeypatch, verb, locked):
    """Prevent leftover runtime directories from blocking revocation after account deletion."""
    host = cards.host
    host.admit_runtime("alice")
    record = host.records()["alice"]
    record["locked"] = locked
    host.record("alice", record)
    host.accounts.pop("alice")
    lookup = cards.scope["pwd"].getpwnam

    def passwd(user):
        if user == "alice":
            raise KeyError(user)
        return lookup(user)

    monkeypatch.setattr(cards.scope["pwd"], "getpwnam", passwd)
    host.execute([verb, "alice"], None)
    assert not host.path("/run/porelo-host/people/alice").exists()
    assert ("forge_lock", ("alice",)) in cards.calls
    assert ("matrix_expel_revoke", ("alice",)) in cards.calls
    assert ("alice" not in host.records()) == (verb == "purge")
    if verb == "lock":
        assert host.records()["alice"]["locked"]


@pytest.mark.parametrize("other", ["record", "entry", "later-entry", "duplicate"])
def test_purged_revocations_cannot_steal_keys_or_repeat_logins(cards, other):
    """Prevent a purged login from revoking another person's key or sharing its revoked key."""
    host = cards.host
    host.write(host.path("/etc/porelo-host/people/purged"), "carol\n", 0o600)
    entries = {
        "record": [person("carol", 2, revoked=True)],
        "entry": [person("dan", 7), person("carol", 7, revoked=True)],
        "later-entry": [person("carol", 7, revoked=True), person("dan", 7)],
        "duplicate": [person("carol", 7, revoked=True), person("carol", 8, revoked=True)],
    }[other]
    refused = []
    persons, revoked = host.registry_persons(entries, None, refused)
    if other == "record":
        assert persons == []
        keys = []
        host.write_krl = lambda values: keys.extend(values)
        host.apply_registry_cards(persons, revoked, host.records())
        assert ssh_key(2) not in keys
        assert not host.records()["alice"]["locked"]
    else:
        assert len(persons) == 1
        assert persons[0]["login"] == ("dan" if other == "entry" else "carol")
    assert any(("named twice" if other == "duplicate" else "key belongs to another person") in r for r in refused)


@pytest.mark.parametrize("field,value", [("ssh", ssh_key(7)), ("expires", "2027-01-01")])
@pytest.mark.parametrize("user", ["ada", "alice"])
def test_lagging_bundle_preserves_membership_and_signers_until_matching_card(cards, field, value, user):
    """Prevent registry rotation from locking a sole-project admin or losing signer history."""
    host = cards.host
    sync(cards)
    record = host.records()[user]
    record["members"] = ["alpha project-admin" if user == "ada" else "alpha developer"]
    host.record(user, record)
    original = dict(record)
    state = host.path("/etc/porelo-host/signers/alpha.json")
    before = json.loads(state.read_text())
    entry = next(p for p in cards.reply["persons"] if p["login"] == user)
    registry_card(cards, dict(entry, **{field: value}))
    record[field] = value
    host.record(user, record)
    answer = sync(cards)
    assert user not in answer["dropped"]
    assert host.records()[user]["members"] == original["members"]
    assert not host.records()[user]["locked"]
    assert json.loads(state.read_text())["current"][user] == before["current"][user]
    assert any(user in r and "does not match" in r for r in answer["refused"])
    entry[field] = value
    sync(cards)
    after = json.loads(state.read_text())
    assert after["current"][user][field] == value
    if field == "ssh":
        assert any(item["login"] == user and item["ssh"] == original["ssh"] for item in after["history"])


@pytest.mark.parametrize("verb", ["lock", "purge", "direct-lock"])
@pytest.mark.parametrize("program", ["gpasswd", "loginctl", "usermod", "systemctl"])
def test_retried_lock_requires_every_executable_before_changes(cards, verb, program):
    """Prevent a lock retry from executing an unchecked or missing privileged program."""
    host = cards.host
    host.commands.update({"gpasswd", "userdel"})
    host.commands.discard("porelo")
    record = host.records()["alice"]
    record["locked"] = True
    host.record("alice", record)
    host.commands.remove(program)
    with pytest.raises(cards.scope["Refusal"], match=program):
        if verb == "direct-lock":
            host.lock("alice", record, False)
        else:
            host.execute([verb, "alice"], None)
    assert cards.calls == []


@pytest.mark.parametrize("membership_state", ["ahead", "missing"])
def test_lagging_bundle_preserves_signers_after_partial_publication(cards, membership_state):
    """Prevent a failed sync's membership state from replacing or deleting deferred signer keys."""
    host = cards.host
    sync(cards)
    state = host.path("/etc/porelo-host/signers/alpha.json")
    before = json.loads(state.read_text())
    publish = host.project_signers

    def failed_publication(*args, **kwargs):
        raise cards.scope["Refusal"]("signer publication failed", 73)

    host.project_signers = failed_publication
    cards.reply["persons"][1]["ssh"] = ssh_key(7)
    registry_card(cards, cards.reply["persons"][1])
    with pytest.raises(cards.scope["Refusal"], match="signer publication failed"):
        sync(cards)
    host.project_signers = publish
    if membership_state == "missing":
        host.path("/etc/porelo-host/projects/alpha.people.json").unlink()
    registry_card(cards, dict(cards.reply["persons"][1], ssh=ssh_key(8)))
    answer = sync(cards)
    after = json.loads(state.read_text())
    assert any("alice" in r and "does not match" in r for r in answer["refused"])
    assert after["current"]["alice"] == before["current"]["alice"]
    assert after["history"] == before["history"]
