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

from test_porelo_host_person import ssh_key, fingerprint
from porelo_host_person_follow_support import prepare_follow, revoke

SCRIPT = Path(__file__).resolve().parents[3] / "roles/porelo/files/porelo-host-person"


@pytest.fixture
def cards(tmp_path, monkeypatch):
    scope = runpy.run_path(str(SCRIPT), run_name="card_tests")
    host = scope["Host"]()
    host.root, host.owner, host.group = tmp_path, os.getuid(), os.getgid()
    for uid in (1200, 1201):  # The service accounts' user managers, each with its session bus.
        (tmp_path / f"run/user/{uid}").mkdir(parents=True, exist_ok=True)
        os.mknod(tmp_path / f"run/user/{uid}/bus", stat.S_IFSOCK | 0o600)
    for name in ("run", "run/user", "run/user/1200", "run/user/1201"):
        host.path("/" + name).chmod(0o755)
    host.euid = 0
    host.accounts = {"alice": 1000, "bob": 1001, "charlie": 1002}
    host.groups = {"porelo-people"}
    host.now = lambda: datetime.datetime(2026, 10, 30, tzinfo=datetime.timezone.utc)
    calls = []

    def commands(args, input=None):
        calls.append((args, input))
        if args[0] == "ssh-keygen":
            return subprocess.run(args, input=input, text=True, capture_output=True, check=False)
        if args[0] == "useradd":
            host.accounts[args[-1]] = max(host.accounts.values()) + 1
        if args[0] == "userdel":
            host.accounts.pop(args[-1], None)
        return subprocess.CompletedProcess(args, 0, "", "")

    host.runner = commands
    host.commands = {"gpasswd", "usermod", "loginctl", "systemctl", "runuser", "env", "porelo", "systemd-run", "pgrep"}
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
    persons = [person("alice", 1, role="admin"), person("bob", 2), person("charlie", 3)]
    records = [("alice", 1, ["host-admin"]), ("bob", 2, ["beta developer"]), ("charlie", 3, ["beta developer"])]
    for user, number, members in records:
        host.write(
            host.path(f"/etc/porelo-host/people/{user}.conf"),
            "".join(f"member={member}\n" for member in members) + f"locked=false\nssh={ssh_key(number)}\nexpires=\n",
            0o600,
        )
    host.write(
        host.path("/etc/porelo-host/projects/alpha.conf"),
        f"admin=alice\nsigned_by={ssh_key(9)}\npublisher=porelo-publisher-alpha\n",
        0o600,
    )
    reply = {
        "revision": "a" * 40,
        "host_card": {"host": "host", "services": {"forge": {"web_port": 3000, "git_port": 2222}}},
        "admins": [{"login": "alice", "key": ssh_key(1), "fingerprint": fingerprint(ssh_key(1)), "backup": False}],
        "persons": [
            {"login": p["login"], "key": p["ssh"], "expires": p["expires"], "revoked": p["revoked"]} for p in persons
        ],
        "projects": [
            {
                "project": "alpha",
                "address": "git@example.org:acme/alpha.git",
                "members": [
                    {"login": "alice", "role": "admin", "locked": False},
                    {"login": "bob", "role": "developer", "locked": False},
                ],
                "signing_keys": [signing_key("alice", 1, "admin"), signing_key("bob", 2)],
            },
            {
                "project": "beta",
                "address": "git@example.org:acme/beta.git",
                "members": [
                    {"login": "bob", "role": "developer", "locked": False},
                    {"login": "charlie", "role": "developer", "locked": False},
                ],
                "signing_keys": [signing_key("bob", 2), signing_key("charlie", 3)],
            },
        ],
    }
    state = prepare_follow(
        host,
        reply,
        lambda args, input: calls.append((args, input)),
        host.runner,
        {
            "alpha": {
                "signers": signer_lines("alice", 1) + signer_lines("bob", 2),
                "certifiers": f'task:alpha:* cert-authority,namespaces="git" {ssh_key(1)}\n',
            },
            "beta": {
                "signers": signer_lines("bob", 2) + signer_lines("charlie", 3),
                "certifiers": f'task:beta:* cert-authority,namespaces="git" {ssh_key(3)}\n',
            },
        },
    )
    host.runner = state
    host.forge_configuration = lambda user: ("forge", [user])
    host.forge_unlock = lambda user: calls.append(("unlock", user))
    host.forge_has_project = lambda project, admin: True
    host.arm_pushes = lambda project: None
    host.follow_push_configs = lambda *args: None
    host.forge_project_apply = lambda project, admin, desired: calls.append(("teams", (project, desired)))
    # The host keeps no Matrix room's members: the gate admits by login; a call here is recorded so tests see it.
    host.matrix_members = lambda project, desired: calls.append(("rooms", (project, desired)))
    host.key_revoked = lambda key: False
    state.calls, state.scope = calls, scope
    return state


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


def signing_key(login, number, role="developer", **values):
    return {
        "login": login,
        "role": role,
        "key": ssh_key(number),
        "valid_from": "2026-01-01",
        "valid_until": None,
        "revoked_since": None,
        **values,
    }


def signer_lines(login, number, before=None):
    """Write a supplied signer and task CA deadline without deriving eligibility from organization data."""
    bound = "" if before is None else f',valid-before="{before}"'
    return (
        f'{login} namespaces="git"{bound} {ssh_key(number)}\n'
        f'task:* cert-authority,namespaces="git"{bound} {ssh_key(number)}\n'
    )


def card(cards, login="bob"):
    return next(p for p in cards.reply["persons"] if p["login"] == login)


def membership(cards, login="bob", project="alpha"):
    return next(
        m for p in cards.reply["projects"] if p["project"] == project for m in p["members"] if m["login"] == login
    )


def follow(cards):
    return cards.host.execute(["org", "follow"], b"")


def test_project_lock_removes_only_its_authority_and_let_back_in_restores_it(cards):
    """Prevent a project admin from ending another project's sessions or retaining its own signers."""
    follow(cards)
    cards.calls.clear()
    membership(cards)["locked"] = True
    cards.signers["alpha"]["signers"] = signer_lines("alice", 1)
    follow(cards)
    record = cards.host.records()["bob"]
    assert record["members"] == ["beta developer"] and not record["locked"]
    assert not any(call[0] in ("forge_lock", "matrix_expel_revoke") for call in cards.calls)
    assert not any(isinstance(call[0], list) and "terminate-user" in call[0] for call in cards.calls)
    assert not any(call[0] == "rooms" for call in cards.calls)
    assert "bob" not in cards.host.read(cards.host.path("/etc/porelo-host/signers/alpha.allowed"))
    membership(cards)["locked"] = False
    cards.signers["alpha"]["signers"] = signer_lines("alice", 1) + signer_lines("bob", 2)
    follow(cards)
    assert "alpha developer" in cards.host.records()["bob"]["members"]
    assert not any(call[0] == "rooms" for call in cards.calls)


def test_signers_are_project_local_and_rotation_preserves_only_history(cards):
    """Prevent cross-project signing and unrestricted task CA signatures after key replacement."""
    follow(cards)
    path = cards.host.path("/etc/porelo-host/signers/alpha.allowed")
    text = path.read_text()
    assert "bob " in text and "charlie " not in text and ssh_key(9) not in text
    assert 'task:* cert-authority,namespaces="git"' in text
    assert stat.S_IMODE(path.stat().st_mode) == 0o644
    card(cards)["key"] = ssh_key(4)
    cards.reply["projects"][0]["signing_keys"][1]["valid_until"] = "2026-10-30"
    cards.reply["projects"][0]["signing_keys"].append(signing_key("bob", 4))
    cards.signers["alpha"]["signers"] = (
        signer_lines("alice", 1) + signer_lines("bob", 2, "20261030000000Z") + signer_lines("bob", 4)
    )
    follow(cards)
    lines = path.read_text().splitlines()
    assert any(ssh_key(2) in line and "valid-before=" in line for line in lines)
    assert all("valid-before=" in line for line in lines if ssh_key(2) in line)


@pytest.mark.parametrize("reason", ["current-key", "last-membership"])
def test_host_loss_ends_sessions_and_revokes_tokens(cards, reason):
    """Prevent existing tunnels or forge credentials from surviving host-wide removal."""
    follow(cards)
    if reason == "last-membership":
        for project in cards.reply["projects"]:
            project["members"] = [m for m in project["members"] if m["login"] != "bob"]
        follow(cards)
    elif reason == "current-key":
        cards.host.key_revoked = lambda key: key == ssh_key(2)
        follow(cards)
    assert cards.host.records()["bob"]["locked"]
    assert ("forge_lock", ("bob",)) in cards.calls
    assert any(isinstance(call[0], list) and call[0][:2] == ["loginctl", "terminate-user"] for call in cards.calls)


def test_an_old_revoked_key_does_not_lock_the_current_person(cards):
    """Prevent a replaced historical key in the KRL from blocking the current card."""
    cards.host.key_revoked = lambda key: key == ssh_key(8)
    follow(cards)
    assert not cards.host.records()["bob"]["locked"]
    assert not any(call[0] == "forge_lock" for call in cards.calls)


def test_purged_login_is_refused_without_blocking_another_lock(cards):
    """Prevent identity reuse while keeping other revocations effective in the same intake."""
    cards.host.write(cards.host.path("/etc/porelo-host/people/purged"), "bob\n", 0o600)
    membership(cards, "alice")["locked"] = True
    card(cards, "charlie")["revoked"] = True
    follow(cards)
    assert "alpha developer" not in cards.host.records()["bob"]["members"]
    assert cards.host.records()["bob"]["locked"]
    assert cards.host.records()["charlie"]["locked"]


def test_card_expiry_replaces_authorized_key(cards):
    """Prevent SSH access from outliving the person's card."""
    card(cards)["expires"] = "2027-01-02"
    follow(cards)
    path = cards.host.path("/etc/ssh/authorized_keys/bob")
    assert path.read_text() == f'expiry-time="20270102000000Z" {ssh_key(2)}\n'


def test_purge_records_a_permanent_private_tombstone(cards):
    """Prevent a removed Linux account from being silently recreated under the same login."""
    host = cards.host
    record = host.records()["bob"]
    host.purge("bob", record, False, True)
    path = host.path("/etc/porelo-host/people/purged")
    assert path.read_text() == "bob\n"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert "bob" not in host.records()
    assert "bob" not in host.accounts
    follow(cards)
    assert "bob" not in host.records() and "bob" not in host.accounts


@pytest.mark.parametrize("login", ["porelo", "porelo-bob", "Alice", "../bob"])
def test_reserved_or_unsafe_logins_are_never_admitted(cards, login):
    """Prevent fetched cards from taking over service accounts or escaping root's paths."""
    cards.reply["persons"].append({"login": login, "key": ssh_key(5), "expires": None, "revoked": False})
    cards.reply["projects"][0]["members"].append({"login": login, "role": "developer", "locked": False})
    with pytest.raises(cards.scope["Refusal"]):
        follow(cards)
    assert login not in cards.host.records()


def test_signer_directory_is_readable_by_the_forge(cards):
    """Prevent root's signer publication from being unreachable to the forge account."""
    follow(cards)
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
    assert json.loads(answer.stdout) == ["alice (host-admin)", "bob (beta developer)", "charlie (beta developer)"]


def test_people_group_drops_unrecorded_and_locked_logins(cards, monkeypatch):
    """Prevent stale supplementary membership from granting socket forwarding or sudo to an unadmitted account."""
    monkeypatch.setattr(
        cards.scope["grp"], "getgrnam", lambda name: SimpleNamespace(gr_mem=["alice", "bob", "charlie", "outsider"])
    )
    follow(cards)
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


def test_failed_service_lock_cannot_be_undone_by_project_follow(cards):
    """Prevent a failed external revocation from leaving a host lock writable by a project admin."""
    follow(cards)

    def unavailable(user):
        raise cards.scope["Refusal"]("fixture service unavailable", 69)

    cards.host.hooks["forge_lock"] = unavailable
    with pytest.raises(cards.scope["Refusal"]):
        revoke(cards)
    cards.host.hooks["forge_lock"] = lambda user: None
    follow(cards)
    assert cards.host.records()["bob"]["locked"]
    assert not cards.host.path("/etc/ssh/authorized_keys/bob").exists()


def test_rotated_history_never_extends_the_previous_cards_expiry(cards):
    """Prevent replacement from extending the period in which an expired old key can sign."""
    card(cards)["expires"] = "2026-11-01"
    cards.reply["projects"][0]["signing_keys"][1]["valid_until"] = "2026-11-01"
    cards.signers["alpha"]["signers"] = signer_lines("alice", 1) + signer_lines("bob", 2, "20261101000000Z")
    follow(cards)
    cards.host.now = lambda: datetime.datetime(2026, 11, 2, tzinfo=datetime.timezone.utc)
    card(cards).update(key=ssh_key(4), expires=None)
    cards.reply["projects"][0]["signing_keys"].append(signing_key("bob", 4))
    cards.signers["alpha"]["signers"] += signer_lines("bob", 4)
    follow(cards)
    old = [
        line
        for line in cards.host.path("/etc/porelo-host/signers/alpha.allowed").read_text().splitlines()
        if ssh_key(2) in line
    ]
    assert len(old) == 2
    assert all('valid-before="20261101000000Z"' in line for line in old)


def test_a_key_cannot_be_shared_with_a_person_of_another_project(cards):
    """Prevent a card from authenticating as an unrelated already admitted login."""
    cards.reply["persons"].append({"login": "eve", "key": ssh_key(3), "expires": None, "revoked": False})
    cards.reply["projects"][0]["members"].append({"login": "eve", "role": "developer", "locked": False})
    with pytest.raises(cards.scope["Refusal"]):
        follow(cards)
    assert "eve" not in cards.host.records()


def test_krl_updates_keep_all_previously_revoked_keys(cards):
    """Prevent organization refresh or key rotation from reviving an already revoked key."""
    host = cards.host
    host.commands.add("ssh-keygen")
    host.runner = lambda args, input=None: subprocess.run(
        args, input=input, text=True, capture_output=True, check=False
    )
    host.key_revoked = cards.scope["Host"].key_revoked.__get__(host)
    host.write_krl([ssh_key(8)])
    host.write_krl([ssh_key(7)])
    host.write_krl([])
    assert host.key_revoked(ssh_key(8))
    assert host.key_revoked(ssh_key(7))
    assert not host.key_revoked(ssh_key(2))


def test_lock_skips_membership_files_of_unregistered_projects(cards):
    """Prevent orphaned project state from permanently blocking host lock and purge."""
    follow(cards)
    cards.host.write(
        cards.host.path("/etc/porelo-host/projects/alpha.people.json"), json.dumps({"bob": person("bob", 2)}), 0o600
    )
    cards.host.path("/etc/porelo-host/projects/alpha.conf").unlink()
    revoke(cards)
    assert cards.host.records()["bob"]["locked"]
    cards.host.accounts.pop("bob")
    cards.host.execute(["purge", "bob"], None)
    assert "bob" not in cards.host.records()


def test_verified_admin_role_is_recorded_as_the_project_admin_membership(cards):
    """Prevent Porelo's admin role from being refused or recorded under a name the host's records do not hold."""
    follow(cards)
    assert "alpha project-admin" in cards.host.records()["alice"]["members"]


def test_an_unusable_role_refuses_its_project_while_other_memberships_apply(cards):
    """Prevent a fetched role outside admin and developer from admitting anyone or blocking unrelated memberships."""
    membership(cards, "alice")["role"] = "project-admin"
    answer = follow(cards)
    assert next(project for project in answer["projects"] if project["project"] == "alpha")["state"] == "refused"
    assert "alpha project-admin" not in cards.host.records()["alice"]["members"]
    assert "beta developer" in cards.host.records()["bob"]["members"]


@pytest.mark.parametrize(
    "target",
    ["authorized", "people", "allowed"],
)
def test_root_publications_and_lock_refuse_symlinks(cards, target, tmp_path):
    """Prevent root publication or revocation from following or removing an untrusted link."""
    host = cards.host
    follow(cards)
    paths = {
        "authorized": "/etc/ssh/authorized_keys/bob",
        "people": "/etc/porelo-host/organization/projects/alpha.json",
        "allowed": "/etc/porelo-host/signers/alpha.allowed",
    }
    path = host.path(paths[target])
    outside = tmp_path / "outside"
    path.unlink()
    path.symlink_to(outside)
    with pytest.raises(cards.scope["Refusal"]):
        if target == "authorized":
            host.lock("bob", host.records()["bob"], False)
        else:
            follow(cards)
    assert path.is_symlink()


@pytest.mark.parametrize("verb", ["lock", "purge"])
def test_locked_record_without_linux_account_can_be_locked_or_purged(cards, verb):
    """Prevent a missing Linux account from crashing recovery of a recorded lock."""
    host = cards.host
    record = host.records()["bob"]
    record["locked"] = True
    host.record("bob", record)
    host.accounts.pop("bob")
    authorized = host.path("/etc/ssh/authorized_keys/bob")
    host.write(authorized, ssh_key(2) + "\n", 0o644)
    if verb == "lock":
        host.lock("bob", host.records()["bob"], None)
    else:
        host.execute([verb, "bob"], None)
    assert not authorized.exists()
    assert (verb == "purge") == ("bob" not in host.records())
    assert not any(isinstance(args, list) and args[0] == "usermod" for args, _ in cards.calls)


def test_purged_revocation_still_enters_the_krl(cards):
    """Prevent a purged person's newly supplied revoked key from remaining usable elsewhere."""
    host = cards.host
    host.write(host.path("/etc/porelo-host/people/purged"), "carol\n", 0o600)
    cards.reply["persons"].append({"login": "carol", "key": ssh_key(7), "expires": None, "revoked": True})
    keys = []
    host.write_krl = keys.extend
    follow(cards)
    assert ssh_key(7) in keys


@pytest.mark.parametrize("other", ["entry", "record"])
def test_org_refuses_keys_owned_by_another_login(cards, other):
    """Prevent shared credentials from granting access as a different person."""
    entries = [
        {"login": "carol", "key": ssh_key(7), "expires": None, "revoked": False},
        {"login": "dan", "key": ssh_key(7), "expires": None, "revoked": False},
    ]
    if other == "record":
        entries = [{**entries[0], "key": ssh_key(2)}]
    cards.reply["persons"].extend(entries)
    with pytest.raises(cards.scope["Refusal"]):
        follow(cards)
    assert "carol" not in cards.host.records() and "dan" not in cards.host.records()


def test_follow_does_not_restore_a_locked_person_without_an_account(cards):
    """Prevent a stale record from causing Linux commands or runtime admission for a missing account."""
    host = cards.host
    record = host.records()["bob"]
    record.update(locked=True, reason="membership")
    host.record("bob", record)
    host.accounts.pop("bob")
    follow(cards)
    assert host.records()["bob"]["locked"]
    assert not any(isinstance(args, list) and args[0] == "usermod" and args[-1] == "bob" for args, _ in cards.calls)


def test_lock_removes_local_and_forge_access_before_project_cleanup(cards):
    """Prevent slow project dependencies from prolonging gate access or Forgejo token validity."""
    follow(cards)
    cards.calls.clear()
    revoke(cards)
    teams = next(index for index, call in enumerate(cards.calls) if call[0] == "teams")
    gate = next(
        index for index, call in enumerate(cards.calls) if call[0] == ["gpasswd", "--delete", "bob", "porelo-people"]
    )
    forge = next(index for index, call in enumerate(cards.calls) if call[0] == "forge_lock")
    assert gate < teams and forge < teams


@pytest.mark.parametrize("verb", ["lock", "purge"])
def test_missing_passwd_account_does_not_crash_locked_record_recovery(cards, monkeypatch, verb):
    """Prevent production passwd lookup from crashing recovery when no injected account map exists."""
    host = cards.host
    record = host.records()["bob"]
    record["locked"] = True
    host.record("bob", record)
    host.accounts = None
    authorized = host.path("/etc/ssh/authorized_keys/bob")
    host.write(authorized, ssh_key(2) + "\n", 0o644)
    lookup = cards.scope["pwd"].getpwnam

    def passwd(user):
        if user == "bob":
            raise KeyError(user)
        return lookup(user)

    monkeypatch.setattr(cards.scope["pwd"], "getpwnam", passwd)
    if verb == "lock":
        host.lock("bob", record, True)
    else:
        host.purge("bob", record, True, False)
    assert not authorized.exists()
    assert not any(
        isinstance(args, list) and args[0] in ("usermod", "loginctl", "systemctl", "runuser") for args, _ in cards.calls
    )


@pytest.mark.parametrize("verb", ["lock", "purge"])
@pytest.mark.parametrize("locked", [False, True])
def test_missing_account_with_runtime_still_allows_revocation(cards, monkeypatch, verb, locked):
    """Prevent leftover runtime directories from blocking revocation after account deletion."""
    host = cards.host
    host.admit_runtime("bob")
    record = host.records()["bob"]
    record["locked"] = locked
    host.record("bob", record)
    host.accounts.pop("bob")
    lookup = cards.scope["pwd"].getpwnam

    def passwd(user):
        if user == "bob":
            raise KeyError(user)
        return lookup(user)

    monkeypatch.setattr(cards.scope["pwd"], "getpwnam", passwd)
    if verb == "lock":
        host.lock("bob", host.records()["bob"], None)
    else:
        host.execute([verb, "bob"], None)
    assert not host.path("/run/porelo-host/people/bob").exists()
    assert ("forge_lock", ("bob",)) in cards.calls
    assert (("matrix_expel_revoke", ("bob",)) in cards.calls) == (verb == "purge")
    assert ("bob" not in host.records()) == (verb == "purge")
    if verb == "lock":
        assert host.records()["bob"]["locked"]


@pytest.mark.parametrize("other", ["record", "entry", "later-entry", "duplicate"])
def test_purged_revocations_cannot_steal_keys_or_repeat_logins(cards, other):
    """Prevent a purged login from revoking another person's key or sharing its revoked key."""
    host = cards.host
    host.write(host.path("/etc/porelo-host/people/purged"), "carol\n", 0o600)

    def entry(login, number, revoked=False):
        return {"login": login, "key": ssh_key(number), "expires": None, "revoked": revoked}

    entries = {
        "record": [entry("carol", 2, True)],
        "entry": [entry("dan", 7), entry("carol", 7, True)],
        "later-entry": [entry("carol", 7, True), entry("dan", 7)],
        "duplicate": [entry("carol", 7, True), entry("carol", 8, True)],
    }[other]
    cards.reply["persons"].extend(entries)
    keys = []
    host.write_krl = keys.extend
    with pytest.raises(cards.scope["Refusal"]):
        follow(cards)
    assert ssh_key(2) not in keys
    assert not host.records()["bob"]["locked"]


@pytest.mark.parametrize("verb", ["follow", "purge", "direct-lock"])
@pytest.mark.parametrize("program", ["gpasswd", "loginctl", "usermod", "systemctl"])
def test_retried_lock_never_executes_a_missing_program(cards, verb, program):
    """Prevent a lock retry from executing an unchecked or missing privileged program."""
    host = cards.host
    host.commands.update({"gpasswd", "userdel"})
    host.commands.discard("porelo")
    record = host.records()["bob"]
    record.update(locked=True, lock="pending", reason="membership")
    host.record("bob", record)
    if verb == "follow":
        host.commands.add("porelo")
    host.commands.remove(program)
    with pytest.raises(cards.scope["Refusal"], match=program):
        if verb == "direct-lock":
            host.lock("bob", record, False)
        elif verb == "follow":
            revoke(cards)
        else:
            host.execute([verb, "bob"], None)
    assert not any(isinstance(args, list) and args[0] == program for args, _ in cards.calls)
    if verb != "purge":
        assert any(isinstance(args, list) and args[0] != program for args, _ in cards.calls)


@pytest.mark.parametrize("membership_state", ["ahead", "missing"])
def test_lagging_state_preserves_signers_after_partial_publication(cards, membership_state):
    """Prevent a failed publication from replacing or deleting deferred signer keys."""
    host = cards.host
    follow(cards)
    path = host.path("/etc/porelo-host/signers/alpha.allowed")
    before = path.read_text()
    publish = host.follow_publish
    attempts = []

    def failed_publication(*args):
        attempts.append(True)
        raise cards.scope["Refusal"]("signer publication failed", 73)

    host.follow_publish = failed_publication
    card(cards)["key"] = ssh_key(7)
    with pytest.raises(cards.scope["Refusal"], match="signer publication failed"):
        follow(cards)
    assert attempts
    host.follow_publish = publish
    if membership_state == "missing":
        host.path("/etc/porelo-host/organization/projects/alpha.json").unlink()
    card(cards)["key"] = ssh_key(8)
    follow(cards)
    assert path.read_text() == before


@pytest.mark.parametrize("dependency", ["forge", "porelo"])
def test_lock_removes_local_access_before_service_dependencies(cards, dependency):
    """Prevent a missing external dependency from leaving live SSH access or group membership."""
    host = cards.host
    follow(cards)
    if dependency == "forge":
        host.hooks["forge_lock"] = host.forge_lock
        host.write(host.path("/etc/porelo-host/forge.conf"), "host=host\naccount=invalid!\n", 0o600)
    else:
        host.commands.discard("porelo")
    cards.calls.clear()
    with pytest.raises(cards.scope["Refusal"]):
        host.lock("bob", host.records()["bob"], True)
    assert not host.path("/etc/ssh/authorized_keys/bob").exists()
    assert host.records()["bob"]["locked"]
    commands = [args for args, _ in cards.calls if isinstance(args, list)]
    assert ["gpasswd", "--delete", "bob", "porelo-people"] in commands
    assert ["loginctl", "terminate-user", "bob"] in commands
    assert ["usermod", "--lock", "--expiredate", "1", "bob"] in commands
    with pytest.raises(cards.scope["Refusal"]):
        host.lock("bob", host.records()["bob"], True)


@pytest.mark.parametrize("program", ["groupadd", "usermod"])
def test_join_groups_refuses_unchecked_privileged_commands(cards, program):
    """Prevent group admission through an executable that failed the ownership check."""
    host = cards.host
    host.commands.add("groupadd")
    host.commands.remove(program)
    with pytest.raises(cards.scope["Refusal"], match=program):
        host.join_groups("bob", set())
    assert not any(isinstance(args, list) and args[0] == program for args, _ in cards.calls)


@pytest.mark.parametrize("program", ["env", "runuser"])
def test_service_account_commands_require_their_wrappers(cards, program):
    """Prevent privileged service commands from executing an unchecked runtime wrapper."""
    host = cards.host
    host.commands.add("env")
    host.commands.remove(program)
    with pytest.raises(cards.scope["Refusal"], match=program):
        host.as_account("porelo-matrix", ["service-command"])
    assert cards.calls == []


@pytest.mark.parametrize("admission", ["add", "follow"])
def test_failed_admission_removes_access_with_missing_revocation_dependency(cards, admission):
    """Prevent failed admission rollback from leaving a live account in porelo-people."""
    host = cards.host
    host.commands.update({"useradd", "groupadd"})
    host.accounts["carol"] = 1003
    joined = set()
    runner = host.runner

    def commands(args, input=None):
        if args[:3] == ["usermod", "--append", "--groups"]:
            joined.add(args[-1])
        elif args[:2] == ["gpasswd", "--delete"]:
            joined.discard(args[2])
        return runner(args, input=input)

    host.runner = commands
    host.create_account = lambda user: host.accounts.__setitem__(user, 1003)
    host.hooks["matrix_expel_revoke"] = host.matrix_expel_revoke
    host.commands.discard(cards.scope["TRANSPORT"])

    def failed_grant(*args):
        raise cards.scope["Refusal"]("admission failed", 69)

    host.hooks["forge_admit"] = failed_grant
    with pytest.raises(cards.scope["Refusal"], match="admission failed"):
        if admission == "add":
            host.add(
                "carol",
                {"ssh": ssh_key(8), "expires": None},
                host.groups,
                "100000-165535",
                "100000-165535",
                members=["alpha developer"],
            )
        else:
            host.accounts.pop("carol")
            cards.reply["persons"].append({"login": "carol", "key": ssh_key(8), "expires": None, "revoked": False})
            cards.reply["projects"][0]["members"].append({"login": "carol", "role": "developer", "locked": False})
            follow(cards)
    assert "carol" not in joined
    assert not host.path("/etc/ssh/authorized_keys/carol").exists()
    assert host.records()["carol"]["locked"]
    assert any(args == ["usermod", "--lock", "--expiredate", "1", "carol"] for args, _ in cards.calls)


def test_a_person_follow_admits_gets_their_daemon_started(cards):
    """Prevent a developer the project's follow admits from having no porelod for their tunnel."""
    host = cards.host
    host.commands.update({"useradd", "groupadd"})
    host.create_account = lambda user: host.accounts.__setitem__(user, 1003)
    started = []
    host.start_daemon = started.append
    cards.reply["persons"].append({"login": "carol", "key": ssh_key(8), "expires": None, "revoked": False})
    cards.reply["projects"][0]["members"].append({"login": "carol", "role": "developer", "locked": False})
    follow(cards)
    assert host.records()["carol"]["members"] == ["alpha developer"]
    assert started == ["carol"]
    follow(cards)
    assert started == ["carol"], "a person already admitted is not set up again at each follow"


def test_a_person_a_follow_unlocks_gets_their_daemon_started_again(cards):
    """Prevent a person a follow unlocks from finding the daemon their lock stopped still down."""
    host = cards.host
    follow(cards)
    record = host.records()["bob"]
    record.update(locked=True, reason="membership")
    host.record("bob", record)
    started = []
    host.start_daemon = started.append
    follow(cards)
    assert not host.records()["bob"]["locked"]
    assert started == ["bob"]
    assert any(args == ["usermod", "--comment", ",,,,umask=0022", "bob"] for args, _ in cards.calls)


def test_follow_existing_unlock_requires_usermod_before_execution(cards):
    """Prevent an existing person's unlock from running an unchecked executable."""
    host = cards.host
    follow(cards)
    record = host.records()["bob"]
    record.update(locked=True, reason="membership")
    host.record("bob", record)
    paths = [host.path("/etc/ssh/authorized_keys/bob"), host.path("/etc/porelo-host/people/bob.conf")]
    before = [(path.read_bytes(), path.stat().st_ino, path.stat().st_mtime_ns) for path in paths]
    host.commands.remove("usermod")
    cards.calls.clear()
    with pytest.raises(cards.scope["Refusal"], match="usermod"):
        host.follow_admit(
            "bob", record, record["members"], person("bob", 2), host.groups, host.records(), host.accounts
        )
    assert [(path.read_bytes(), path.stat().st_ino, path.stat().st_mtime_ns) for path in paths] == before
    assert not any(isinstance(args, list) and args[0] == "usermod" for args, _ in cards.calls)


@pytest.mark.parametrize("task_fails", [False, True])
def test_task_cleanup_restores_expiry_after_running_with_access_removed(cards, task_fails):
    """Prevent PAM expiry from blocking cleanup forever or cleanup failure from leaving an unexpired account."""
    host = cards.host
    follow(cards)
    expired, manager_running, task_stops = False, True, []
    runner = host.runner

    def commands(args, input=None):
        nonlocal expired, manager_running
        if args[:2] == ["usermod", "--lock"]:
            expired = True
        elif args[:2] == ["usermod", "--expiredate"]:
            expired = args[2] != ""
        elif args[:2] == ["systemctl", "stop"]:
            manager_running = False
        elif args[:2] == ["systemctl", "start"]:
            manager_running = True
        elif args[0] == "runuser":
            assert not host.path("/etc/ssh/authorized_keys/bob").exists()
            assert host.records()["bob"]["locked"]
            assert any(call[0] == ["gpasswd", "--delete", "bob", "porelo-people"] for call in cards.calls)
            if expired or not manager_running or task_fails:
                return subprocess.CompletedProcess(args, 1, "", "")
            task_stops.append(args)
        return runner(args, input=input)

    host.runner = commands
    if task_fails:
        with pytest.raises(cards.scope["Refusal"], match="runuser"):
            host.lock("bob", host.records()["bob"], True)
    else:
        host.lock("bob", host.records()["bob"], True)
        assert task_stops
    assert expired and not manager_running


def test_untrusted_porelo_cannot_prevent_local_lock(cards):
    """Prevent executable ownership refusal from aborting removal before SSH access is revoked."""
    host = cards.host
    follow(cards)
    available = host.available

    def checked(program):
        if program == "porelo":
            raise cards.scope["Refusal"]("untrusted porelo executable", 69)
        return available(program)

    host.available = checked
    with pytest.raises(cards.scope["Refusal"], match="untrusted porelo"):
        host.lock("bob", {**host.records()["bob"], "reason": "membership"}, True)
    assert not host.path("/etc/ssh/authorized_keys/bob").exists()
    assert host.records()["bob"]["locked"]


@pytest.mark.parametrize("retry", ["follow", "refresh", "lock", "purge"])
def test_unfinished_revocation_is_durable_and_retried(cards, retry):
    """Prevent a failed service revocation from disappearing on subsequent reconciliation."""
    host = cards.host
    follow(cards)
    previous_members = list(host.records()["bob"]["members"])
    for project in cards.reply["projects"]:
        project["members"] = [m for m in project["members"] if m["login"] != "bob"]
    host.hooks["forge_lock"] = lambda user: (_ for _ in ()).throw(cards.scope["Refusal"]("forge unavailable", 69))
    with pytest.raises(cards.scope["Refusal"]):
        follow(cards)
    rec = host.records()["bob"]
    assert rec.get("lock") == "pending"
    assert rec["members"] == previous_members
    cards.calls.clear()
    host.hooks["forge_lock"] = lambda user: cards.calls.append(("retried", user))
    if retry == "follow":
        follow(cards)
    elif retry == "refresh":
        host.execute(["org", "refresh"], b"")
    elif retry == "lock":
        host.lock("bob", host.records()["bob"], None)
    else:
        host.execute([retry, "bob"], None)
    assert ("retried", "bob") in cards.calls


def test_failed_local_rollback_reports_unfinished_removal(cards):
    """Prevent reporting a safely locked account when rollback left local access in place."""
    host = cards.host
    host.create_account = lambda user: None
    host.grant = lambda *args: (_ for _ in ()).throw(cards.scope["Refusal"]("grant failed", 69))
    host.remove_runtime = lambda user: (_ for _ in ()).throw(cards.scope["Refusal"]("runtime unsafe", 73))
    with pytest.raises(cards.scope["Refusal"], match="local account removal failed; retry lock"):
        host.add("bob", {"ssh": ssh_key(2), "expires": None}, set(), None, None, members=["beta developer"])
    assert not host.records()["bob"]["locked"]


def test_follow_continues_revoking_after_one_person_fails(cards):
    """Prevent one unavailable service from preserving another revoked person's access."""
    host = cards.host
    follow(cards)
    for project in cards.reply["projects"]:
        project["members"] = [m for m in project["members"] if m["login"] not in ("bob", "charlie")]

    def failing(user):
        if user == "bob":
            raise cards.scope["Refusal"]("forge unavailable", 69)

    host.hooks["forge_lock"] = failing
    with pytest.raises(cards.scope["Refusal"], match="bob"):
        follow(cards)
    assert host.records()["charlie"]["locked"]
    assert not any(call[0] == "rooms" for call in cards.calls)


@pytest.mark.parametrize("reason", ["key", "membership"])
def test_unlock_drops_tokens_before_restoring_access(cards, reason):
    """Prevent tokens surviving an earlier incomplete or automatic lock from becoming usable again."""
    host = cards.host
    follow(cards)
    rec = host.records()["bob"]
    rec.update(locked=True, reason=reason)
    host.record("bob", rec)
    host.forge_unlock = lambda user: cards.calls.append(("unlock", user))
    cards.calls.clear()
    follow(cards)
    assert cards.calls.index(("forge_drop_tokens", ("bob",))) < cards.calls.index(("unlock", "bob"))


@pytest.mark.parametrize("expiry", ["2026-01-01", "2026-11-01"])
def test_deferred_access_is_bounded_by_org_expiry(cards, expiry):
    """Prevent stale cards extending admission or signing authority past the current card."""
    host = cards.host
    follow(cards)
    card(cards)["expires"] = expiry
    cards.signers["alpha"]["signers"] = signer_lines("alice", 1) + signer_lines("bob", 2, host.card_expiry(expiry))
    follow(cards)
    if expiry == "2026-01-01":
        assert "alpha developer" not in host.records()["bob"]["members"]
    else:
        assert 'valid-before="20261101000000Z"' in host.path("/etc/porelo-host/signers/alpha.allowed").read_text()


def test_lagging_demotion_removes_admin_authority(cards):
    """Prevent a key lag from preserving a role explicitly demoted by verified access."""
    membership(cards)["role"] = "admin"
    follow(cards)
    card(cards)["key"] = ssh_key(7)
    membership(cards)["role"] = "developer"
    follow(cards)
    assert "alpha project-admin" not in cards.host.records()["bob"]["members"]
    assert "alpha developer" in cards.host.records()["bob"]["members"]
    assert (
        next(args[1]["bob"]["role"] for name, args in reversed(cards.calls) if name == "teams" and args[0] == "alpha")
        == "developer"
    )


@pytest.mark.parametrize("unsafe", ["runtime", "tmpfiles", "key"])
def test_follow_revocation_isolates_unsafe_paths(cards, unsafe):
    """Prevent one unsafe path from blocking independent root revocation steps."""
    host = cards.host
    follow(cards)
    path = host.path(
        {
            "runtime": "/run/porelo-host/people/bob",
            "tmpfiles": "/etc/tmpfiles.d/porelo-person-bob.conf",
            "key": "/etc/ssh/authorized_keys/bob",
        }[unsafe]
    )
    if path.is_dir():
        import shutil

        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)
    path.symlink_to(host.root / "outside")
    with pytest.raises(cards.scope["Refusal"]):
        revoke(cards)
    assert (["gpasswd", "--delete", "bob", "porelo-people"], None) in cards.calls
    assert ("forge_lock", ("bob",)) in cards.calls


def test_direct_lock_without_optional_porelo_finishes(cards):
    """Prevent an absent optional task CLI from making revocation permanently fail."""
    cards.host.commands.remove("porelo")
    cards.host.lock("bob", cards.host.records()["bob"], False)
    assert cards.host.records()["bob"]["locked"]


@pytest.mark.parametrize("operation", ["clear", "purge"])
@pytest.mark.parametrize("failure", [OSError, RuntimeError])
def test_vault_cleanup_restores_expiry_and_manager_on_any_exception(cards, operation, failure):
    """Prevent failed vault cleanup leaving an unexpired account or a running user manager."""
    host = cards.host
    command = host.command
    host.lock = lambda *args: None

    def failing(args, **kwargs):
        if (operation == "clear" and "vault" in args) or (
            operation == "purge" and args[:2] == ["loginctl", "disable-linger"]
        ):
            raise failure("cleanup failed")
        return command(args, **kwargs)

    host.command = failing
    with pytest.raises(failure):
        if operation == "clear":
            host.clear_vault("bob")
        else:
            host.purge("bob", host.records()["bob"], True, True)
    assert (["usermod", "--expiredate", "1", "bob"], None) in cards.calls
    assert (["systemctl", "stop", "user@1001.service"], None) in cards.calls


@pytest.mark.parametrize("program", ["loginctl", "systemctl"])
def test_direct_end_sessions_requires_programs(cards, program):
    """Prevent unchecked privileged commands through the public integration method."""
    cards.host.commands.remove(program)
    with pytest.raises(cards.scope["Refusal"], match=program):
        cards.host.end_sessions("bob")
    assert not cards.calls


def test_purge_checks_env_before_mutation(cards):
    """Prevent task cleanup dependency failure after starting destructive purge work."""
    cards.host.commands.add("userdel")
    cards.host.commands.remove("env")
    with pytest.raises(cards.scope["Refusal"], match="env"):
        cards.host.execute(["purge", "bob"], None)
    assert not cards.calls


def test_pending_local_lock_cannot_readmit_or_authorize_person(cards):
    """Prevent a failed local removal being mistaken for an unlocked admission."""
    host = cards.host
    follow(cards)
    host.remove_runtime = lambda user: (_ for _ in ()).throw(cards.scope["Refusal"]("unsafe runtime", 73))
    with pytest.raises(cards.scope["Refusal"]):
        host.lock("bob", host.records()["bob"], True)
    cards.calls.clear()
    with pytest.raises(cards.scope["Refusal"]):
        host.person("bob", host.records())
    with pytest.raises(cards.scope["Refusal"], match="bob"):
        follow(cards)
    assert not any(
        args[:2] == ["usermod", "--append"] and args[-1] == "bob" for args, _ in cards.calls if isinstance(args, list)
    )


def test_deferred_demotion_without_membership_file(cards):
    """Prevent a missing publication from preserving a demoted administrator's local authority."""
    membership(cards)["role"] = "admin"
    follow(cards)
    card(cards)["key"] = ssh_key(7)
    membership(cards)["role"] = "developer"
    cards.host.path("/etc/porelo-host/organization/projects/alpha.json").unlink()
    follow(cards)
    assert "alpha project-admin" not in cards.host.records()["bob"]["members"]


def test_deferred_signer_without_membership_file_has_org_bound(cards):
    """Prevent partial publication bypassing the current card's signing deadline."""
    host = cards.host
    follow(cards)
    card(cards)["expires"] = "2026-11-01"
    cards.signers["alpha"]["signers"] = signer_lines("alice", 1) + signer_lines("bob", 2, "20261101000000Z")
    host.path("/etc/porelo-host/organization/projects/alpha.json").unlink()
    follow(cards)
    matching = [
        line
        for line in host.path("/etc/porelo-host/signers/alpha.allowed").read_text().splitlines()
        if ssh_key(2) in line
    ]
    assert len(matching) == 2
    assert all('valid-before="20261101000000Z"' in line for line in matching)


def test_pending_local_lock_cannot_regain_runtime(cards):
    """Prevent maintenance from restoring access while local removal remains unfinished."""
    host = cards.host
    follow(cards)
    host.remove_runtime = lambda user: (_ for _ in ()).throw(cards.scope["Refusal"]("unsafe runtime", 73))
    with pytest.raises(cards.scope["Refusal"]):
        host.lock("bob", host.records()["bob"], True)
    cards.calls.clear()
    host.admit_runtime = lambda user: cards.calls.append(("admitted", user)) or 1
    host.execute(["restore-runtime"], None)
    assert ("admitted", "bob") not in cards.calls


@pytest.mark.parametrize("operation", ["clear", "purge"])
def test_failed_safety_restoration_stays_pending_until_later_follow(cards, operation):
    """Prevent a restarted manager or lifted expiry surviving a failed cleanup without retry intent."""
    host = cards.host
    follow(cards)
    revoke(cards)
    command = host.command
    damaged = False

    def failing(args, **kwargs):
        nonlocal damaged
        if "vault" in args:
            damaged = True
            raise cards.scope["Refusal"]("vault unavailable", 69)
        if damaged and (args[:3] == ["usermod", "--expiredate", "1"] or args[:2] == ["systemctl", "stop"]):
            raise cards.scope["Refusal"]("restoration unavailable", 69)
        return command(args, **kwargs)

    host.command = failing
    with pytest.raises(cards.scope["Refusal"]):
        if operation == "clear":
            host.clear_vault("bob")
        else:
            host.purge("bob", host.records()["bob"], True, True)
    record = host.records()["bob"]
    assert record.get("lock") == "pending"
    assert not record["locked"]
    host.command = command
    cards.calls.clear()
    follow(cards)
    assert ("forge_lock", ("bob",)) in cards.calls
    assert host.records()["bob"]["locked"]
    assert host.records()["bob"].get("lock") is None


def test_task_stop_restoration_failure_records_local_lock_unfinished(cards):
    """Prevent failed temporary-expiry cleanup claiming that all local access is gone."""
    host = cards.host
    follow(cards)
    command = host.command
    restarted = False

    def failing(args, **kwargs):
        nonlocal restarted
        if args[:2] == ["systemctl", "start"]:
            restarted = True
        if restarted and (args[:3] == ["usermod", "--expiredate", "1"] or args[:2] == ["systemctl", "stop"]):
            raise cards.scope["Refusal"]("restoration unavailable", 69)
        return command(args, **kwargs)

    host.command = failing
    with pytest.raises(cards.scope["Refusal"]):
        host.lock("bob", host.records()["bob"], True)
    record = host.records()["bob"]
    assert record.get("lock") == "pending"
    assert not record["locked"]


def test_retry_does_not_forget_project_after_failed_follow_publication(cards):
    """Prevent an updated publication from hiding a failed remote team revocation on retry."""
    host = cards.host
    follow(cards)
    for project in cards.reply["projects"]:
        project["members"] = [member for member in project["members"] if member["login"] != "bob"]
    apply = host.forge_project_apply
    host.forge_project_apply = lambda *args: (_ for _ in ()).throw(cards.scope["Refusal"]("team API unavailable", 69))
    with pytest.raises(cards.scope["Refusal"]):
        follow(cards)
    assert host.records()["bob"]["locked"]
    assert not host.path("/etc/ssh/authorized_keys/bob").exists()
    host.forge_project_apply = apply
    host.write_krl = lambda keys: None
    cards.calls.clear()
    follow(cards)
    assert ("teams", ("alpha", {"alice": membership(cards, "alice")})) in cards.calls


def managers(cards, monkeypatch, groups, containers=(), failing=False):
    """Each person's user manager running with the given supplementary groups, porelo-people being gid 4242.

    The persons named in containers run a container, whose conmon pgrep finds; with failing, a restart fails.
    """
    monkeypatch.setattr(
        cards.scope["grp"], "getgrnam", lambda name: SimpleNamespace(gr_mem=["alice", "bob", "charlie"], gr_gid=4242)
    )
    host, plain = cards.host, cards.host.runner

    def commands(args, input=None):
        if args[0] == "pgrep":
            return subprocess.CompletedProcess(args, 0 if args[2] in containers else 1, "", "")
        if failing and args[:2] == ["systemctl", "restart"]:
            cards.calls.append((args,))
            return subprocess.CompletedProcess(args, 1, "", "")
        if args[:2] in (["systemctl", "show"], ["systemctl", "restart"]):
            pid = 7000 + int(args[-1].removeprefix("user@").removesuffix(".service")) % 1000
            if args[1] == "restart":  # A manager started anew takes the person's groups as they are now.
                host.path(f"/proc/{pid}/status").write_text("Name:\tsystemd\nGroups:\t100 4242\n")
                return plain(args, input=input)
            return subprocess.CompletedProcess(args, 0, f"{pid}\n", "")
        return plain(args, input=input)

    host.runner = commands
    for login, number in (("alice", 0), ("bob", 1), ("charlie", 2)):
        status = host.path(f"/proc/{7000 + number}/status")
        status.parent.mkdir(parents=True, exist_ok=True)
        status.write_text(f"Name:\tsystemd\nGroups:\t{groups}\n")


def task_held(cards, login, before):
    """A task certificate of the person recorded on the host, valid until the given time."""
    directory = cards.host.path(f"/var/lib/porelo-host/tasks/{login}")
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory.chmod(0o700)
    directory.parent.chmod(0o700)
    record = {"task": "one", "login": login, "certificate": "c", "fingerprint": "f", "valid_before": before}
    cards.host.write(directory / "one.json", json.dumps(record), 0o600)


def restarted(cards):
    return [call[0][-1] for call in cards.calls if call[0][:2] == ["systemctl", "restart"]]


def test_a_manager_started_before_its_person_joined_porelo_people_is_restarted(cards, monkeypatch):
    """Prevent porelod running without the group that opens the host's Matrix gate, so a task cannot join its room."""
    managers(cards, monkeypatch, "100")
    follow(cards)
    assert sorted(restarted(cards)) == ["user@1000.service", "user@1001.service", "user@1002.service"]


def test_a_manager_that_holds_porelo_people_is_left_running(cards, monkeypatch):
    """Prevent a follow every five minutes from ending a person's sessions for nothing."""
    managers(cards, monkeypatch, "100 4242")
    follow(cards)
    assert restarted(cards) == []


def test_a_person_with_a_running_container_keeps_the_manager_and_is_told(cards, monkeypatch, capsys):
    """Prevent the restart from ending a running task, however long it runs past its certificate."""
    managers(cards, monkeypatch, "100", containers=("bob",))
    task_held(cards, "bob", "2026-01-01T00:00:00Z")
    follow(cards)
    assert "user@1001.service" not in restarted(cards)
    assert "porelod of bob lacks porelo-people" in capsys.readouterr().err


def test_an_ended_task_whose_certificate_holds_does_not_keep_the_manager(cards, monkeypatch):
    """Prevent a task ended by hand from holding the person without the group until its certificate runs out."""
    managers(cards, monkeypatch, "100")
    task_held(cards, "bob", "2099-01-01T00:00:00Z")
    follow(cards)
    assert "user@1001.service" in restarted(cards)


def test_a_restart_that_fails_is_said_and_the_follow_goes_on(cards, monkeypatch, capsys):
    """Prevent one person's manager failing the follow, the other persons' restarts and its other work with it."""
    managers(cards, monkeypatch, "100", failing=True)
    follow(cards)
    assert sorted(set(restarted(cards))) == ["user@1000.service", "user@1001.service", "user@1002.service"]
    assert "porelod of bob lacks porelo-people and was not restarted" in capsys.readouterr().err
