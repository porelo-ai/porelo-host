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
    host.commands = {"usermod", "loginctl", "systemctl", "runuser", "porelo", "systemd-run"}
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
        sync(cards)
        cards.reply["persons"][1].update(change)
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
    sync(cards)
    cards.host.now = lambda: datetime.datetime(2026, 11, 2, tzinfo=datetime.timezone.utc)
    cards.reply["persons"][1] = person("alice", 4)
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
    with pytest.raises(cards.scope["Refusal"], match="another person"):
        sync(cards)
    assert "eve" not in cards.host.records()


def test_installed_add_refuses_device_input_instead_of_ignoring_it(cards, monkeypatch):
    """Prevent the installed CLI from retaining an alternate device-input admission path."""
    import io

    monkeypatch.setattr(cards.scope["sys"], "stdin", io.TextIOWrapper(io.BytesIO(b"l1 old device input\n")))
    with pytest.raises(cards.scope["Refusal"], match="no credential input"):
        cards.host.execute(["add", "ada", "--role", "project-admin"], None)
