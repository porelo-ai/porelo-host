"""Guard organization intake against replay, access surviving removal, and premature account deletion."""

import copy
import datetime
import contextlib
import json
import subprocess
from pathlib import Path

import pytest

from test_porelo_host_person import snapshot, ssh_key
from porelo_host_person_follow_support import prepare_follow
import test_porelo_host_person_cards

cards = test_porelo_host_person_cards.cards


@pytest.fixture
def following(cards):
    host = cards.host
    for name in ("forge_configuration", "forge_unlock", "forge_has_project", "arm_pushes", "follow_push_configs"):
        delattr(host, name)
    host.key_revoked = cards.scope["Host"].key_revoked.__get__(host)
    reply = {
        "revision": "a" * 40,
        "host_card": {"host": "host"},
        "admins": [
            {
                "login": "alice",
                "key": ssh_key(1),
                "fingerprint": cards.scope["fingerprint"](ssh_key(1)),
                "backup": False,
            }
        ],
        "persons": [
            {"login": login, "key": ssh_key(number), "expires": "2028-11-02", "revoked": False}
            for login, number in (("alice", 1), ("bob", 2), ("charlie", 3))
        ],
        "projects": [
            {
                "project": "alpha",
                "address": "git@example.org:acme/alpha.git",
                "members": [
                    {"login": "bob", "role": "admin", "locked": False},
                    {"login": "charlie", "role": "developer", "locked": False},
                ],
                "signing_keys": [
                    {
                        "login": "bob",
                        "role": "admin",
                        "key": ssh_key(2),
                        "valid_from": "2026-11-02",
                        "valid_until": "2028-11-02",
                        "revoked_since": None,
                    }
                ],
            }
        ],
    }
    runner = host.runner

    def commands(args, input=None):
        if args[0] == "ssh-keygen":
            cards.calls.append((args, input))
            return subprocess.run(args, input=input, text=True, capture_output=True, check=False)
        if args[0] == "userdel":
            host.accounts.pop(args[-1], None)
        if args[0] == "useradd":
            host.accounts[args[-1]] = max(host.accounts.values()) + 1
        return runner(args, input=input)

    state = prepare_follow(
        host,
        reply,
        lambda args, input: cards.calls.append((args, input)),
        commands,
        {
            "alpha": {
                "signers": f'bob namespaces="git" {ssh_key(2)}\n',
                "certifiers": f'task:alpha:* cert-authority,namespaces="git" {ssh_key(2)}\n',
            },
            "beta": {
                "signers": f'charlie namespaces="git" {ssh_key(3)}\n',
                "certifiers": f'task:beta:* cert-authority,namespaces="git" {ssh_key(3)}\n',
            },
        },
    )
    state.calls, state.scope = cards.calls, cards.scope
    host.runner = state
    return state


def raises(error):
    def raising(*args):
        raise error

    return raising


def readers(state, path):
    return state.acls.get(path.stat().st_ino, set())


def test_admission_retry_finishes_subordinate_ids_and_linger(following):
    """Prevent an interrupted admission from unlocking an account whose containers cannot run."""
    host = following.host
    host.path("/etc/porelo-host/people/bob.conf").unlink()
    host.accounts.pop("bob")
    runner = host.runner
    failed = False
    linger = set()

    def commands(args, input=None):
        nonlocal failed
        if args[:2] == ["loginctl", "enable-linger"]:
            linger.add(args[-1])
        if args[:2] == ["loginctl", "disable-linger"]:
            linger.discard(args[-1])
        if args[0] == "usermod" and args[1] in ("--add-subuids", "--add-subgids"):
            if args[1] == "--add-subgids" and not failed:
                failed = True
                raise following.scope["Refusal"]("fixture subordinate GID failure", 69)
            kind = "subuid" if args[1] == "--add-subuids" else "subgid"
            path = host.path("/etc/" + kind)
            start, end = map(int, args[2].split("-"))
            path.write_text(path.read_text() + f"{args[-1]}:{start}:{end - start + 1}\n")
        return runner(args, input=input)

    host.runner = commands
    with pytest.raises(following.scope["Refusal"], match="subordinate GID failure"):
        follow(following)
    assert host.records()["bob"]["locked"]
    # Model a stopped user manager as well as the partial subordinate-ID allocation.
    linger.discard("bob")
    follow(following)
    assert not host.records()["bob"]["locked"]
    assert "bob" in linger
    for kind in ("subuid", "subgid"):
        assert len([row for row in host.subids(kind) if row[0] == "bob"]) == 1


def follow(state, revision=None):
    if revision is not None:
        state.reply["revision"] = revision * 40
    return state.host.execute(["org", "follow"], b"")


def without_refusal(state):
    """The host's files apart from the note of what was refused, which is the one thing a refusal may leave."""
    kept = ("etc/porelo-host/organization", "etc/porelo-host/organization/refused.json")
    return {path: value for path, value in snapshot(state.host.root).items() if str(path) not in kept}


def test_an_older_state_is_refused_without_changing_anything(following):
    """Prevent replay from restoring removed authority or rotating the trust pin backward."""
    state = following
    follow(state)
    follow(state, "b")
    before = snapshot(state.host.root)
    state.reply["revision"] = "a" * 40
    with pytest.raises(state.scope["Refusal"], match="older|refused-state"):
        follow(state)
    assert without_refusal(state) == {
        path: value for path, value in before.items() if path != "etc/porelo-host/organization"
    }
    fetches = [args for args, _input in state.calls if isinstance(args, list) and "fetch" in args]
    assert fetches[-1][fetches[-1].index("--since") + 1] == "b" * 40


def test_a_fetch_refusal_leaves_everything_untouched(following):
    """Prevent a refused ancestry or signature check from mutating even pending locks."""
    follow(following)
    following.exit = 65
    following.stderr = "refused-state: older state served again"
    before = snapshot(following.host.root)
    with pytest.raises(following.scope["Refusal"], match="older state"):
        follow(following)
    assert without_refusal(following) == {
        path: value for path, value in before.items() if path != "etc/porelo-host/organization"
    }


def test_a_fetch_keeps_its_trust_record_across_follows(following):
    """Prevent each follow asking the forge about every person again, or failing for want of a place to write."""
    follow(following)
    fetch = next(args for args, _input in following.calls if isinstance(args, list) and "fetch" in args)
    assert "StateDirectory=porelo-host-org-fetch" in fetch and "StateDirectoryMode=0700" in fetch
    assert "Environment=XDG_STATE_HOME=/var/lib/porelo-host-org-fetch" in fetch


def test_a_refused_state_reaches_the_host_admin_and_keeps_the_state_taken(following):
    """Prevent a removed host or a stolen owner key passing unseen in a journal, or taking the host's state away."""
    follow(following)
    taken = following.host.execute(["org", "status"], b"")
    assert taken["refused"] is None
    following.exit = 65
    following.stderr = "refused-state: the host's files changed, signed by SHA256:owner\x1b[2J"
    with pytest.raises(following.scope["Refusal"]):
        follow(following)
    status = following.host.execute(["org", "status"], b"")
    assert status["refused"] == "refused-state: the host's files changed, signed by SHA256:owner [2J"
    assert {key: value for key, value in status.items() if key != "refused"} == {
        key: value for key, value in taken.items() if key != "refused"
    }
    following.exit = 0
    follow(following, "b")
    assert following.host.execute(["org", "status"], b"")["refused"] is None


def test_a_fetch_that_cannot_say_is_no_refusal_for_the_host_admin(following):
    """Prevent an unreachable forge reading as if the organization had refused this host."""
    follow(following)
    following.exit = 69
    following.stderr = "cannot-say: the forge did not answer"
    with pytest.raises(following.scope["Refusal"]):
        follow(following)
    assert following.host.execute(["org", "status"], b"")["refused"] is None


@pytest.mark.parametrize("damage", ["host", "revision"])
def test_malformed_answers_change_nothing(following, damage):
    """Prevent incomplete untrusted data from deleting memberships or publishing another host's settings."""
    if damage == "host":
        following.reply["host_card"]["host"] = "other"
    else:
        following.reply["revision"] = None
    before = snapshot(following.host.root)
    with pytest.raises(following.scope["Refusal"], match="malformed|another host") as error:
        follow(following)
    assert error.value.code == 65
    assert snapshot(following.host.root) == before


def test_a_revoked_person_is_locked_on_the_next_follow(following):
    """Prevent revoked cards retaining SSH sessions, tokens or project access."""
    follow(following)
    following.reply["persons"][1]["revoked"] = True
    follow(following, "b")
    assert following.host.records()["bob"]["locked"]
    assert not following.host.path("/etc/ssh/authorized_keys/bob").exists()
    assert ("forge_lock", ("bob",)) in following.calls
    assert ("matrix_expel_revoke", ("bob",)) not in following.calls
    key = following.host.path("/tmp/revoked.pub")
    following.host.write(key, ssh_key(2) + "\n", 0o600)
    result = subprocess.run(
        ["ssh-keygen", "-Q", "-f", str(following.host.path("/etc/ssh/porelo-revoked.krl")), str(key)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1 and "REVOKED" in result.stdout


def test_uncarry_locks_only_members_without_another_membership(following):
    """Prevent access surviving the last project, without ending another project's sessions."""
    state = following
    other = copy.deepcopy(state.reply["projects"][0])
    other.update(project="beta", members=[{"login": "charlie", "role": "developer", "locked": False}])
    state.reply["projects"].append(other)
    follow(state)
    state.reply["projects"] = [other]
    follow(state, "b")
    records = state.host.records()
    assert records["bob"]["locked"] and records["bob"]["members"] == []
    assert records["bob"]["locked_on"] == "2026-10-30"
    assert not records["charlie"]["locked"] and records["charlie"]["members"] == ["beta developer"]
    assert not records["alice"]["locked"]
    assert not state.host.path("/etc/porelo-host/organization/projects/alpha.json").exists()


def test_membership_loss_purges_on_the_first_follow_seven_days_later(following):
    """Prevent deletion during the grace period or an abandoned account surviving past it."""
    state = following
    follow(state)
    state.reply["projects"] = []
    follow(state, "b")
    state.host.now = lambda: datetime.datetime(2026, 11, 5, tzinfo=datetime.timezone.utc)
    answer = follow(state)
    assert "bob" in state.host.accounts
    assert next(p for p in answer["persons"] if p["login"] == "bob")["purge_on"] == "2026-11-06"
    state.host.now = lambda: datetime.datetime(2026, 11, 6, tzinfo=datetime.timezone.utc)
    follow(state)
    assert "bob" not in state.host.accounts and "bob" not in state.host.records()
    assert "bob" in state.host.purged()
    assert (["userdel", "--remove", "bob"], None) in state.calls
    assert sum(call == ("matrix_expel_revoke", ("bob",)) for call in state.calls) == 1


def test_readmission_within_seven_days_preserves_the_account(following):
    """Prevent readmission from recreating the account and losing its existing work."""
    state = following
    projects = copy.deepcopy(state.reply["projects"])
    follow(state)
    uid = state.host.accounts["bob"]
    work = state.host.path("/home/bob/unpushed")
    state.host.write(work, "work\n", 0o600)
    state.reply["projects"] = []
    follow(state, "b")
    state.host.now = lambda: datetime.datetime(2026, 11, 5, tzinfo=datetime.timezone.utc)
    state.reply["projects"] = projects
    follow(state, "c")
    assert state.host.accounts["bob"] == uid and work.read_text() == "work\n"
    assert not state.host.records()["bob"]["locked"]
    assert "locked_on" not in state.host.records()["bob"]
    assert not any(args[0] in ("useradd", "userdel") for args, _input in state.calls if isinstance(args, list))


def test_refresh_refuses_a_token_nobody_waits_for(following):
    """Prevent a token being accepted and left unused or leaking through an error."""
    before = snapshot(following.host.root)
    with pytest.raises(following.scope["Refusal"], match="no project waits for a token") as error:
        following.host.execute(["org", "refresh"], b"unused-token\n")
    assert error.value.code == 65
    assert snapshot(following.host.root) == before and not following.calls


@pytest.mark.parametrize("verb", ["follow", "refresh"])
def test_follow_and_refresh_refuse_sudo(following, verb):
    """Prevent a person's sudo privilege reaching root's organization credentials."""
    following.host.sudo_user = "alice"
    with pytest.raises(following.scope["Refusal"], match="never.*sudo") as error:
        following.host.execute(["org", verb], b"")
    assert error.value.code == 65 and not following.calls


def test_project_file_acl_tracks_only_unlocked_members(following):
    """Prevent nonmembers reading private project data and stale ACLs surviving a membership lock."""
    state = following
    answer = follow(state)
    path = state.host.path("/etc/porelo-host/organization/projects/alpha.json")
    expected = {key: state.reply["projects"][0][key] for key in ("project", "address", "signing_keys")}
    expected.update(host="host", revision="a" * 40, fetch_from=None, homeserver=None, room=None)
    assert json.loads(path.read_text()) == expected
    assert readers(state, path) == {1001, 1002}
    assert path.stat().st_mode & 0o077 == 0
    assert answer["projects"] == [{"project": "alpha", "state": "carried", "why": None, "since": "2026-10-30"}]
    state.reply["projects"][0]["members"][0]["locked"] = True
    follow(state, "b")
    assert readers(state, path) == {1002}
    assert state.host.records()["bob"]["locked"]
    state.reply["projects"][0]["members"][0]["locked"] = False
    refreshed = state.host.execute(["org", "refresh"], b"")
    assert refreshed == state.host.execute(["org", "status"], b"")
    assert readers(state, path) == {1001, 1002}


def test_follow_admits_new_accounts_and_publishes_porelos_signers(following):
    """Prevent missing accounts or obsolete signer publications from blocking a newly carried project."""
    state = following
    state.reply["persons"].append({"login": "carol", "key": ssh_key(8), "expires": None, "revoked": False})
    state.reply["projects"][0]["members"].append({"login": "carol", "role": "developer", "locked": False})
    follow(state)
    assert "carol" in state.host.accounts
    assert state.host.records()["carol"]["members"] == ["alpha developer"]
    written = state.host.path("/etc/porelo-host/signers/alpha.certifiers").read_text()
    assert written == f'task:alpha:* cert-authority,namespaces="git" {ssh_key(2)}\n'


def test_a_failed_service_update_cannot_preserve_removed_member_acls(following):
    """Prevent a service outage preserving private project access for a member active elsewhere."""
    state = following
    other = copy.deepcopy(state.reply["projects"][0])
    other.update(project="beta", members=[{"login": "bob", "role": "developer", "locked": False}])
    state.reply["projects"].append(other)
    follow(state)
    state.reply["projects"][0]["members"][0]["locked"] = True
    state.host.follow_memberships = raises(OSError("disk full"))
    with pytest.raises(OSError):
        follow(state, "b")
    path = state.host.path("/etc/porelo-host/organization/projects/alpha.json")
    assert 1001 not in readers(state, path)


def test_a_failed_application_keeps_the_accepted_revision_for_replay_checks(following):
    """Prevent a partial system failure from making an accepted access removal replayable."""
    state = following
    follow(state)
    state.host.follow_forge_members = raises(state.scope["Refusal"]("service failed", 69))
    with pytest.raises(state.scope["Refusal"]):
        follow(state, "b")
    applied = json.loads(state.host.path("/etc/porelo-host/organization/applied.json").read_text())
    assert applied["revision"] == "b" * 40
    state.reply["revision"] = "a" * 40
    with pytest.raises(state.scope["Refusal"], match="older"):
        follow(state)


def test_a_revoked_key_stays_on_the_krl_once_the_state_no_longer_names_the_person(following):
    """Prevent a revoked key working again once the organization stops listing its owner and the account is purged."""
    state = following
    follow(state)
    state.reply["persons"][1]["revoked"] = True
    state.reply["projects"][0]["members"].pop(0)
    follow(state, "b")
    state.reply["persons"].pop(1)
    follow(state, "c")
    state.host.now = lambda: datetime.datetime(2026, 11, 7, tzinfo=datetime.timezone.utc)
    follow(state, "d")
    assert "bob" not in state.host.records()
    follow(state, "e")
    key = state.host.path("/tmp/revoked.pub")
    state.host.write(key, ssh_key(2) + "\n", 0o600)
    result = subprocess.run(
        ["ssh-keygen", "-Q", "-f", str(state.host.path("/etc/ssh/porelo-revoked.krl")), str(key)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert "REVOKED" in result.stdout, "the key must stay revoked after its owner leaves the state"


@pytest.mark.parametrize("revoked", [False, True])
def test_a_listed_member_is_never_purged(following, revoked):
    """Prevent deleting the account and work of someone still listed: locked by an admin, or with a lost key."""
    state = following
    follow(state)
    state.reply["projects"][0]["members"][0]["locked"] = True
    state.reply["persons"][1]["revoked"] = revoked
    answer = follow(state, "b")
    assert state.host.records()["bob"]["locked"]
    assert "purge_on" not in next(p for p in answer["persons"] if p["login"] == "bob")
    state.host.now = lambda: datetime.datetime(2026, 12, 30, tzinfo=datetime.timezone.utc)
    follow(state)
    assert "bob" in state.host.accounts and "bob" not in state.host.purged()


def test_a_person_listed_again_loses_the_purge_day(following):
    """Prevent a purge running on a person who was only locked again after coming back into a project."""
    state = following
    projects = copy.deepcopy(state.reply["projects"])
    follow(state)
    state.reply["projects"][0]["members"].pop(0)
    follow(state, "b")
    assert state.host.records()["bob"]["locked_on"] == "2026-10-30"
    projects[0]["members"][0]["locked"] = True
    state.reply["projects"] = projects
    follow(state, "c")
    assert "locked_on" not in state.host.records()["bob"]


def test_one_failed_lock_does_not_spare_the_next_person(following):
    """Prevent one person's failing removal leaving another removed person with access."""
    state = following
    follow(state)
    state.reply["projects"] = []
    original = state.host.lock

    def lock(user, record, porelo):
        if user == "bob":
            raise state.scope["Refusal"]("bob's lock failed", 69)
        return original(user, record, porelo)

    state.host.lock = lock
    with pytest.raises(state.scope["Refusal"], match="bob's lock failed") as error:
        follow(state, "b")
    assert error.value.code == 69
    assert state.host.records()["charlie"]["locked"]


def test_project_file_names_the_hosts_forge_by_the_project_and_the_central_repository(following, monkeypatch):
    """Prevent a member fetching from a forge path that does not exist: the local organization is the project's."""
    state = following
    state.reply["host_card"]["services"] = {"forge": {"web_port": 3000, "git_port": 2222}}
    state.host.write(state.host.path("/etc/porelo-host/forge.conf"), "host=host\naccount=git\n", 0o600)
    monkeypatch.setattr(state.host, "forge_configuration", lambda user: ("git", [user]))
    monkeypatch.setattr(state.host, "follow_forge_members", lambda *args: None)
    follow(state)
    written = json.loads(state.host.path("/etc/porelo-host/organization/projects/alpha.json").read_text())
    assert written["fetch_from"] == "http://127.0.0.1:2222/alpha/alpha.git"
    assert written["host"] == "host"
    assert state.host.path("/etc/porelo-host/signers/alpha.allowed").exists()


def test_a_host_with_no_forge_writes_certifiers_and_no_allowed_signers(following):
    """Prevent a stale push judge's file standing where nothing judges a push, and the gate losing its certifiers."""
    follow(following)
    assert following.host.path("/etc/porelo-host/signers/alpha.certifiers").exists()
    assert not following.host.path("/etc/porelo-host/signers/alpha.allowed").exists()


def test_room_and_homeserver_stay_null_together_until_the_room_is_kept(following):
    """Prevent a member's transport getting a homeserver with no room, which it cannot use and Porelo cannot refuse."""
    state = following
    state.host.write(state.host.path("/etc/systemd/system/porelo-matrix-gate.socket"), "", 0o644)
    follow(state)
    written = json.loads(state.host.path("/etc/porelo-host/organization/projects/alpha.json").read_text())
    assert written["homeserver"] is None and written["room"] is None


def test_one_projects_bad_address_does_not_stop_a_revocation(following):
    """Prevent one project admin's address keeping a revoked person on the host, by failing the whole follow."""
    state = following
    follow(state)
    state.reply["projects"][0]["address"] = "has spaces"
    state.reply["persons"][2]["revoked"] = True
    answer = follow(state, "b")
    assert state.host.records()["charlie"]["locked"]
    written = json.loads(state.host.path("/etc/porelo-host/organization/projects/alpha.json").read_text())
    assert written["address"] is None and written["fetch_from"] is None
    assert "unusable address" in answer["projects"][0]["why"]
    assert "has spaces" not in answer["projects"][0]["why"]


def test_a_new_account_can_read_its_project_file_after_the_same_follow(following):
    """Prevent a person admitted by this follow finding no project until the next one."""
    state = following
    state.host.path("/etc/porelo-host/people/bob.conf").unlink()
    state.host.accounts.pop("bob")
    follow(state)
    path = state.host.path("/etc/porelo-host/organization/projects/alpha.json")
    assert state.host.accounts["bob"] in readers(state, path)


def test_an_interrupted_follow_takes_the_same_state_again_with_its_new_pin(following, monkeypatch):
    """Prevent a cut-off follow between pin and applied.json from rolling trust back or refusing the same state."""
    state = following
    follow(state)
    applied = state.host.path("/etc/porelo-host/organization/applied.json")
    before = applied.read_bytes()
    state.reply["admins"][0].update(login="charlie", key=ssh_key(3), fingerprint=state.scope["fingerprint"](ssh_key(3)))
    write = state.host.write

    def cut_off(path, *args, **kwargs):
        if path == applied:
            assert state.host.path("/etc/porelo-host/organization/pin").read_text() == f"charlie {ssh_key(3)}\n"
            raise OSError("follow cut off before applied state publication")
        return write(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(state.host, "write", cut_off)
        with pytest.raises(OSError, match="cut off"):
            follow(state, "b")
    assert applied.read_bytes() == before
    assert state.host.path("/etc/porelo-host/organization/pin").read_text() == f"charlie {ssh_key(3)}\n"
    follow(state)
    assert state.pins[-1] == f"charlie {ssh_key(3)}\n"
    assert json.loads(applied.read_text())["commit"] == "b" * 40
    assert state.host.records()["charlie"]["members"] == ["host-admin", "alpha developer"]


def test_nothing_is_followed_until_the_read_key_is_added(following):
    """Prevent the timer failing loudly on a host just set up, and any fetch with a key the forge does not know."""
    state = following
    state.host.path("/etc/porelo-host/organization/read/organization.added").unlink()
    answer = follow(state)
    assert answer["organization"] == "waiting-for-token"
    assert not [args for args, _input in state.calls if isinstance(args, list) and "fetch" in args]
    assert state.host.execute(["org", "refresh"], b"")["organization"] == "waiting-for-token"


def test_refresh_adds_the_read_key_with_the_token_and_keeps_none(following):
    """Prevent the host admin's central token lying on the host, on a command line, or in an answer."""
    state = following
    state.host.path("/etc/porelo-host/organization/read/organization.added").unlink()
    secret = "central-token-123"
    answer = state.host.execute(["org", "refresh"], (secret + "\n").encode())
    assert state.added == [secret]
    assert answer["organization"] == "following" and answer["commit"] == "a" * 40
    assert secret not in json.dumps(answer)
    assert not [args for args, _input in state.calls if isinstance(args, list) and secret in " ".join(args)]
    assert all(secret not in str(item) for item in snapshot(state.host.root).values())
    with pytest.raises(state.scope["Refusal"], match="no project waits for a token"):
        state.host.execute(["org", "refresh"], b"second\n")


def test_a_refused_read_key_stays_waiting(following):
    """Prevent the host claiming to follow when the forge refused its key."""
    state = following
    state.host.path("/etc/porelo-host/organization/read/organization.added").unlink()
    state.add_exit = 65
    with pytest.raises(state.scope["Refusal"]):
        state.host.execute(["org", "refresh"], b"token\n")
    assert state.host.execute(["org", "status"], b"")["organization"] == "waiting-for-token"


def test_a_project_not_yet_on_the_hosts_forge_does_not_fail_the_follow(following, monkeypatch):
    """Prevent every follow failing, and refresh with it, between a project's carrying and its coming onto the forge."""
    state = following
    monkeypatch.setattr(state.host, "forge_configuration", lambda user: ("git", [user]))
    applied = []
    monkeypatch.setattr(state.host, "forge_project_apply", lambda *args: applied.append(args))
    monkeypatch.setattr(state.host, "arm_pushes", lambda project: None)
    monkeypatch.setattr(state.host, "follow_push_configs", lambda *args: None)

    class Session:
        def __enter__(self):
            return "git", None, "http://forge/api/v1/admin/users/", "token"

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(state.host, "forge_session", lambda *args: Session())

    def absent(opener, base, token, method, route, expected, body=None, not_found=None):
        assert route == "orgs/alpha" and not_found
        raise state.scope["Refusal"](not_found, 65)

    monkeypatch.setattr(state.host, "forge_api", absent)
    state.reply["host_card"]["services"] = {"forge": {"web_port": 3000, "git_port": 2222}}
    assert follow(state)["commit"] == "a" * 40
    assert applied == []
    monkeypatch.setattr(state.host, "forge_api", lambda *args, **kwargs: {})
    follow(state)
    assert [args[0] for args in applied] == ["alpha"]


def krl_says(state, number):
    key = state.host.path("/tmp/asked.pub")
    state.host.write(key, ssh_key(number) + "\n", 0o600)
    krl = str(state.host.path("/etc/ssh/porelo-revoked.krl"))
    return subprocess.run(["ssh-keygen", "-Q", "-f", krl, str(key)], capture_output=True, text=True, check=False).stdout


def test_a_replaced_card_lets_the_person_back_and_keeps_the_old_key_revoked(following):
    """Prevent a person with a replaced lost key staying locked out, and the lost key ever working again."""
    state = following
    follow(state)
    state.reply["persons"][1]["revoked"] = True
    follow(state, "b")
    assert state.host.records()["bob"]["locked"]
    state.reply["persons"][1].update(revoked=False, key=ssh_key(9))
    answer = follow(state, "c")
    record = state.host.records()["bob"]
    assert not record["locked"] and record["ssh"] == ssh_key(9)
    assert "bob" not in answer.get("revoked", [])
    assert "REVOKED" in krl_says(state, 2), "the lost key stays revoked for good"
    assert "REVOKED" not in krl_says(state, 9), "the new key must work"


def test_a_revoked_key_answered_as_not_revoked_stays_locked(following):
    """Prevent a state that merely stops saying revoked from reviving the same key."""
    state = following
    follow(state)
    state.reply["persons"][1]["revoked"] = True
    follow(state, "b")
    state.reply["persons"][1]["revoked"] = False
    follow(state, "c")
    assert state.host.records()["bob"]["locked"]
    assert "bob" in json.loads(state.host.path("/etc/porelo-host/organization/applied.json").read_text())["revoked"]


def test_a_key_revoked_only_in_the_last_state_reaches_the_krl_before_its_replacement_is_taken(following):
    """Prevent an interrupted follow losing a revoked key when the next state already replaces the card."""
    state = following
    follow(state)
    state.reply["persons"][1]["revoked"] = True
    state.host.apply_org_cards = raises(OSError("interrupted"))
    with pytest.raises(OSError):
        follow(state, "b")
    del state.host.apply_org_cards
    state.reply["persons"][1].update(revoked=False, key=ssh_key(9))
    follow(state, "c")
    assert "REVOKED" in krl_says(state, 2)


@pytest.mark.parametrize("number, comes_back", [(9, True), (2, False)])
def test_a_person_gone_from_the_state_comes_back_only_under_another_key(following, number, comes_back):
    """Prevent a revoked key returning after a state left its owner out, without stranding a replaced card."""
    state = following
    bob = state.reply["persons"][1]
    membership = state.reply["projects"][0]["members"].pop(0)
    state.reply["projects"][0]["members"].append(dict(membership))
    follow(state)
    bob["revoked"] = True
    follow(state, "b")
    state.reply["persons"].pop(1)
    state.reply["projects"][0]["members"] = [m for m in state.reply["projects"][0]["members"] if m["login"] != "bob"]
    follow(state, "c")
    state.reply["persons"].insert(1, {**bob, "revoked": False, "key": ssh_key(number)})
    state.reply["projects"][0]["members"].append(dict(membership))
    follow(state, "d")
    assert state.host.records()["bob"]["locked"] is not comes_back


def push_config_host(following, repositories):
    """The follow's push config step with the forge's list given, and each command as a person kept."""
    host = following.host
    host.write(host.path("/etc/porelo-host/forge.conf"), "host=host\ngit_port=3001\n", 0o644)
    host.write(host.path("/etc/porelo-host/forge/central-ca.conf"), "/etc/ssl/certs/ca-certificates.crt\n", 0o644)
    host.forge_pages = lambda *args: repositories

    @contextlib.contextmanager
    def session(*args):
        yield "porelo-forge", None, "http://localhost/api/v1/admin/users/", "token"

    host.forge_session = session
    written = []
    host.as_account = lambda login, arguments, **kwargs: written.append((login, arguments, kwargs.get("input")))
    return host, written


@pytest.mark.parametrize("name", ["code", "Code"])
def test_a_members_push_config_is_written_as_that_member_and_goes_with_the_membership(following, name):
    """Prevent root writing through a link in a person's home, or a gone member keeping the project's addresses."""
    address = f"https://forge.example.org/alpha/{name}.git"
    host, written = push_config_host(following, [{"name": name, "original_url": address}])
    host.follow_push_configs("alpha", "alice", ["alice"], ["bob"], {"alice": 1000, "bob": 1001}, True)
    (login, arguments, text), (gone, removal, nothing) = written
    assert login == "alice" and arguments[-1] == "alpha" and arguments[0] == "sh"
    assert text.splitlines()[1:] == [
        "local http://127.0.0.1:3001",
        "owner alpha",
        "central-ca /etc/ssl/certs/ca-certificates.crt",
        f"repository {name} {address}",
    ]
    assert gone == "bob" and "rm -f" in removal[2] and removal[-1] == "alpha" and nothing is None


@pytest.mark.parametrize("address", ["", None, "http://forge.example/a.git", "https://user@forge.example/a.git"])
def test_a_repository_with_no_central_address_writes_no_push_config(following, address):
    """Prevent a person's push reaching for an address the migration never recorded, or one carrying a credential."""
    host, written = push_config_host(following, [{"name": "code", "original_url": address}])
    with pytest.raises(following.scope["Refusal"], match="no valid central address"):
        host.follow_push_configs("alpha", "alice", ["alice"], [], {"alice": 1000}, True)
    assert not written


def test_a_project_taken_off_writes_no_config_and_takes_each_away(following):
    """Prevent a project no longer on the card leaving push configs that still name it."""
    host, written = push_config_host(following, [])
    host.follow_push_configs("alpha", "alice", [], ["alice"], {"alice": 1000}, False)
    assert [(item[0], item[1][-1]) for item in written] == [("alice", "alpha")]
    assert "rm -f" in written[0][1][2]


def test_a_member_nobody_vouches_for_yet_gets_no_access_and_stops_nothing(following):
    """Prevent a first-seen member, named with no card, from refusing the whole state or being admitted."""
    following.reply["projects"][0]["members"].append({"login": "carol", "role": "developer", "locked": False})
    follow(following)
    assert "carol" not in following.host.records()
    assert not following.host.records()["alice"]["locked"]


def test_root_renews_the_pin_and_the_next_follow_keeps_it(following):
    """Prevent a host staying refused for good after an owner replaced its admin's card, or a follow undoing the renewal."""
    follow(following)
    following.exit = 65
    following.stderr = "refused-state: abc replaced a host admin's card"
    with pytest.raises(following.scope["Refusal"]):
        follow(following)
    applied_path = following.host.path("/etc/porelo-host/organization/applied.json")
    before = applied_path.read_bytes()
    answer = following.host.execute(["org", "renew-pin"], f"alice {ssh_key(9)}\n".encode())
    assert answer["refused"] is None
    pin = following.host.path("/etc/porelo-host/organization/pin")
    assert pin.read_text() == f"alice {ssh_key(9)}\n"
    assert applied_path.read_bytes() == before, "renewal must not rewrite the accepted organization"
    following.exit = 1
    following.stderr = "stop here"
    with pytest.raises(following.scope["Refusal"]):
        follow(following)
    assert pin.read_text() == f"alice {ssh_key(9)}\n", "a failed fetch must preserve the renewed pin"


@pytest.mark.parametrize(
    "supplied",
    [b"", b"alice\n", b"root ssh-ed25519 AAAA\n", "alice not-a-key\n".encode(), "ä".encode()],
)
def test_a_renewal_with_no_valid_key_changes_nothing(following, supplied):
    """Prevent a mistyped renewal leaving the host with no admin, or a reader of root's files a way in."""
    follow(following)
    before = snapshot(following.host.root)
    with pytest.raises(following.scope["Refusal"], match="pin") as error:
        following.host.execute(["org", "renew-pin"], supplied)
    assert error.value.code == 65
    assert snapshot(following.host.root) == before


def test_a_renewal_is_roots_alone(following):
    """Prevent a person's sudo moving the trust the whole host follows."""
    follow(following)
    following.host.sudo_user = "alice"
    with pytest.raises(following.scope["Refusal"], match="root's alone"):
        following.host.execute(["org", "renew-pin"], f"alice {ssh_key(9)}\n".encode())


@pytest.mark.parametrize("scopes", [None, "read:organization"])
def test_every_forge_session_token_can_delete_itself(following, scopes):
    """Prevent a narrow token failing its own deletion through the admin API, and so every follow, on a real forge."""
    host = following.host
    made = []
    host.forge_configuration = lambda user: ("porelo-forge", [user])
    host.forge_endpoint = lambda: ("http://localhost/api/v1/admin/users/", None)
    host.forge_opener = lambda endpoint: None
    host.forge_token = lambda account, user, given, name: made.append(given) or "token"
    host.forge_drop_named = lambda *args: None
    with host.forge_session("alice", scopes) if scopes else host.forge_session("alice"):
        pass
    assert "write:admin" in made[0].split(",")
    assert scopes is None or scopes in made[0].split(",")


def test_a_person_this_follow_admits_reads_their_project_file_at_once(following):
    """Prevent a new member's project file staying unreadable for the five minutes to the next follow."""
    host = following.host
    real = host.accounts
    host.account_ids = lambda: dict(real)
    following.reply["persons"].append({"login": "dave", "key": ssh_key(7), "expires": "2028-11-02", "revoked": False})
    following.reply["projects"][0]["members"].append({"login": "dave", "role": "developer", "locked": False})
    follow(following)
    path = host.path("/etc/porelo-host/organization/projects/alpha.json")
    assert real["dave"] in following.acls[path.stat().st_ino]


@pytest.mark.parametrize("code", [69, 75, 1])
def test_a_fetch_that_says_nothing_is_no_refusal(following, code):
    """Prevent a hung forge showing the host admin a refusal to judge, and a wait reading as Porelo's refusal."""
    following.exit = code
    following.stderr = "cannot-say: the forge is away"
    with pytest.raises(following.scope["Refusal"]) as error:
        follow(following)
    assert error.value.code == 69
    assert not following.host.path("/etc/porelo-host/organization/refused.json").exists()


@pytest.mark.parametrize(
    "words",
    [
        ["org", "follow"],
        ["org", "refresh"],
        ["org", "renew-pin"],
    ],
    ids=["follow", "refresh", "renew-pin"],
)
def test_a_taken_over_project_admin_can_admit_nobody(following, words):
    """Prevent a project admin's account, once taken over, admitting a person the organization's signer did not list."""
    follow(following)
    before = sorted(following.host.records())
    following.host.sudo_user = "bob"
    with pytest.raises(following.scope["Refusal"]):
        following.host.execute(words, f"mallory {ssh_key(9)}\n".encode())
    assert sorted(following.host.records()) == before
    assert following.host.path("/etc/porelo-host/organization/pin").read_text() != f"mallory {ssh_key(9)}\n"


def test_the_sudoers_rules_give_people_no_verb_that_admits():
    """Prevent a sudoers rule ever handing a person the verbs that decide who is on the host."""
    rules = (Path(__file__).parents[3] / "roles/porelo/files/porelo-host-person.sudoers").read_text()
    verbs = {line.split("porelo-host-person ")[1].split()[0] for line in rules.splitlines() if "NOPASSWD" in line}
    assert verbs == {"forge-token", "task", "arrivals"}


def test_lock_preserves_the_matrix_account_for_a_person_brought_back(following):
    """Prevent a follow lock from deleting the Matrix account a returning person still needs."""
    state = following
    matrix_accounts = {"bob"}
    state.host.hooks["matrix_expel_revoke"] = matrix_accounts.remove
    follow(state)
    member = state.reply["projects"][0]["members"][0]
    member["locked"] = True
    follow(state)
    assert state.host.records()["bob"]["locked"]
    assert not state.host.path("/etc/ssh/authorized_keys/bob").exists()
    assert matrix_accounts == {"bob"}
    member["locked"] = False
    follow(state)
    assert not state.host.records()["bob"]["locked"]
    assert state.host.path("/etc/ssh/authorized_keys/bob").exists()
    assert matrix_accounts == {"bob"}


def test_purge_retries_matrix_expulsion_before_deleting_the_record(following):
    """Prevent a refused Matrix expulsion from losing the person record needed to retry purge."""
    state = following
    follow(state)
    attempts = []

    def expel(login):
        attempts.append(login)
        if len(attempts) == 1:
            raise state.scope["Refusal"]("Matrix expulsion refused", 69)

    state.host.hooks["matrix_expel_revoke"] = expel
    with pytest.raises(state.scope["Refusal"], match="Matrix expulsion refused"):
        state.host.execute(["purge", "bob"], b"")
    assert attempts == ["bob"]
    assert "bob" in state.host.records() and "bob" in state.host.accounts
    assert state.host.records()["bob"]["locked"]
    assert not any(isinstance(args, list) and args[0] == "userdel" for args, given in state.calls)
    assert state.host.execute(["purge", "bob"], b"") == {"person": "bob", "purged": True}
    assert attempts == ["bob", "bob"]
    assert "bob" not in state.host.records() and "bob" not in state.host.accounts


@pytest.mark.parametrize("login", ["root", "daemon", "existing", "Alice", "-alice", "../alice", "a" * 33, "a\n"])
def test_account_names_cannot_take_over_an_existing_account(following, login):
    """Prevent organization admission from taking over root, system accounts, unrelated accounts or unsafe paths."""
    state = following
    state.host.accounts.update(root=0, daemon=1, existing=1003)
    before = dict(state.host.accounts)
    state.reply["persons"].append({"login": login, "key": ssh_key(9), "expires": None, "revoked": False})
    state.reply["projects"][0]["members"].append({"login": login, "role": "developer", "locked": False})
    with pytest.raises(state.scope["Refusal"]):
        follow(state)
    assert state.host.accounts == before
    assert login not in state.host.records()
    assert not any(
        isinstance(args, list) and args[0] in ("useradd", "usermod", "userdel") and args[-1] == login
        for args, given in state.calls
    )


def project_services(state, monkeypatch, *, forge=True, gate=True):
    """Stand in for the root helper and the gate, with independent physical project records."""
    host = state.host
    host.now = lambda: datetime.datetime(2026, 11, 3, tzinfo=datetime.timezone.utc)
    host.path("/etc/porelo-host/projects/alpha.conf").unlink(missing_ok=True)
    actions, rooms = [], []
    host.commands.update({"podman", "cat"})
    if forge:
        host.write(host.path("/etc/porelo-host/forge.conf"), "host=host\naccount=porelo-forge\n", 0o600)
    if gate:
        host.write(host.path("/etc/systemd/system/porelo-matrix-gate.socket"), "[Socket]\n", 0o644)
    monkeypatch.setattr(
        host, "forge_has_project", lambda name, admin: host.path(f"/etc/porelo-host/projects/{name}.conf").exists()
    )
    monkeypatch.setattr(host, "forge_project_apply", lambda *args: None)
    monkeypatch.setattr(host, "arm_pushes", lambda *args: [])
    monkeypatch.setattr(host, "follow_push_configs", lambda *args: None)

    def helper(arguments, supplied=None):
        actions.append((arguments, supplied))
        verb, name = arguments[:2]
        path = host.path(f"/etc/porelo-host/projects/{name}.conf")
        if verb == "add":
            host.write(
                path, f"admin={arguments[2]}\nsigned_by={arguments[4]}\npublisher=porelo-publisher-{name}\n", 0o600
            )
        elif verb == "remove":
            path.unlink()
        return {}

    def room(verb, name, persons):
        rooms.append((verb, name, persons))
        return {"homeserver": "unix:/run/porelo-matrix/client.sock", "room": f"#{name}:matrix.example.org"}

    monkeypatch.setattr(host, "follow_project_command", helper, raising=False)
    monkeypatch.setattr(host, "follow_room_command", room, raising=False)
    return actions, rooms


def test_a_host_without_services_admits_a_project_without_running_service_commands(following, monkeypatch):
    """Prevent optional forge and gate services from blocking admission or running an unwanted command."""
    actions, rooms = project_services(following, monkeypatch, forge=False, gate=False)
    following.reply["persons"].append({"login": "dave", "key": ssh_key(7), "expires": "2028-11-02", "revoked": False})
    following.reply["projects"][0]["members"].append({"login": "dave", "role": "developer", "locked": False})
    answer = follow(following)
    assert following.host.records()["dave"]["members"] == ["alpha developer"]
    assert following.host.path("/etc/ssh/authorized_keys/dave").exists()
    assert not following.host.records()["bob"]["locked"]
    assert answer["projects"][0]["state"] == "carried"
    assert actions == rooms == []


def test_a_new_project_registers_its_own_admin_and_waits_for_refresh(following, monkeypatch):
    """Prevent registering under the host admin or using a central token before refresh supplies it."""
    actions, rooms = project_services(following, monkeypatch)
    answer = follow(following)
    assert actions == [(["add", "alpha", "bob", "--signed-by", ssh_key(2)], None)]
    assert answer["projects"][0]["state"] == "waiting-for-token"
    assert rooms == [("keep-room", "alpha", ["bob", "charlie"])]
    path = following.host.path("/etc/porelo-host/organization/projects/alpha.json")
    assert json.loads(path.read_text())["room"] == "#alpha:matrix.example.org"
    follow(following)
    assert [args[0] for args, unused in actions] == ["add"], "registration is not repeated while waiting"


def test_a_replaced_host_admin_loses_roots_login(following):
    """Prevent a host admin the organization replaced from keeping root's login with their old key."""
    follow(following)
    root = following.host.path("/etc/ssh/authorized_keys/root")
    departed = following.reply["admins"][0]["key"]
    assert root.read_text() == departed + "\n"
    following.reply["admins"][0].update(
        login="charlie", key=ssh_key(3), fingerprint=following.scope["fingerprint"](ssh_key(3))
    )
    follow(following, "b")
    assert departed not in root.read_text(), "the departed admin must lose root access"
    assert root.read_text() == ssh_key(3) + "\n"
    assert root.stat().st_mode & 0o777 == 0o644


def test_a_purge_on_a_host_with_no_homeserver_needs_no_transport(following, monkeypatch):
    """Prevent a host without Matrix from never finishing a person's purge."""

    def no_account(name):
        raise KeyError(name)

    monkeypatch.setattr(following.scope["pwd"], "getpwnam", no_account)
    following.host.matrix_expel_revoke("bob")
    assert not [args for args, unused in following.calls if isinstance(args, list) and args[0] == "runuser"]


def test_a_room_that_lost_someone_is_named_in_the_journal(following, monkeypatch, capsys):
    """Prevent keep-room's answer, which names Matrix accounts, from reading as no room, or the removal going unseen."""
    host = following.host
    host.commands.update({"cat", "env", "runuser", following.scope["TRANSPORT"]})
    monkeypatch.setattr(host, "matrix_admin_token", lambda: "matrix-fixture-admin-token")
    answer = {"room": "#porelo-alpha:matrix.example.org", "removed": ["@porelo.bob:matrix.example.org"]}
    monkeypatch.setattr(
        host, "runner", lambda arguments, input=None: subprocess.CompletedProcess(arguments, 0, json.dumps(answer), "")
    )
    kept = host.follow_room_command("keep-room", "alpha", [])
    assert kept["room"] == answer["room"] and kept["homeserver"] == "unix:/run/porelo-matrix/client.sock"
    assert "alpha: out of its room: @porelo.bob:matrix.example.org" in capsys.readouterr().err


def test_a_failed_migration_keeps_nobody_out_of_the_room(following, monkeypatch):
    """Prevent a central forge that is away from leaving a project's members with no room until the next follow."""
    unused, rooms = project_services(following, monkeypatch)
    host = following.host
    follow(following)
    rooms.clear()
    original = host.follow_project_command

    def refused(arguments, supplied=None):
        if arguments[0] == "migrate":
            raise following.scope["Refusal"]("the central forge is away", 69)
        return original(arguments, supplied)

    monkeypatch.setattr(host, "follow_project_command", refused)
    host.path("/etc/porelo-host/organization/projects/alpha.json").unlink()
    with contextlib.suppress(following.scope["Refusal"]):
        host.execute(["org", "refresh"], b"central-fixture-private-token\n")
    assert rooms == [("keep-room", "alpha", ["bob", "charlie"])]
    project = next(item for item in host.org_status("host")["projects"] if item["project"] == "alpha")
    assert project["state"] == "waiting-for-token" and "the central forge is away" in project["why"]
    written = json.loads(host.path("/etc/porelo-host/organization/projects/alpha.json").read_text())
    assert written["room"] == "#alpha:matrix.example.org"


def test_refresh_consumes_the_token_only_for_waiting_migrations(following, monkeypatch, capsys):
    """Prevent a central token reaching an argument, diagnostic or file, or being reused by a timer."""
    actions, unused = project_services(following, monkeypatch, gate=False)
    follow(following)
    token = "central-fixture-private-token"
    answer = following.host.execute(["org", "refresh"], (token + "\n").encode())
    assert answer["projects"][0]["state"] == "carried"
    assert [(args, supplied) for args, supplied in actions if args[0] == "migrate"] == [
        (["migrate", "alpha"], {"address": "git@example.org:acme/alpha.git", "token": token})
    ]
    follow(following)
    assert len([args for args, unused in actions if args[0] == "migrate"]) == 1
    assert token not in str([args for args, unused in actions])
    assert token not in str(following.calls) + str(answer) + str(capsys.readouterr())
    assert all(token.encode() not in path.read_bytes() for path in following.host.root.rglob("*") if path.is_file())


def test_an_interrupted_registration_is_retried_from_the_physical_record(following, monkeypatch):
    """Prevent an accepted revision from hiding an unfinished project registration on the next follow."""
    actions, unused = project_services(following, monkeypatch, gate=False)
    helper = following.host.follow_project_command

    def interrupted(arguments, supplied=None):
        helper(arguments, supplied)
        raise OSError("interrupted after registration")

    monkeypatch.setattr(following.host, "follow_project_command", interrupted)
    with pytest.raises(OSError):
        follow(following)
    monkeypatch.setattr(following.host, "follow_project_command", helper)
    answer = follow(following)
    assert answer["projects"][0]["state"] == "waiting-for-token"
    assert [args[0] for args, unused in actions] == ["add"]


def test_an_unpushed_project_is_held_then_removed_after_the_push(following, monkeypatch):
    """Prevent taking local-only work off the forge, or forgetting to retry a held project's removal."""
    actions, rooms = project_services(following, monkeypatch)
    follow(following)
    following.reply["projects"] = []
    helper = following.host.follow_project_command

    def held(arguments, supplied=None):
        if arguments[0] == "remove":
            raise following.scope["Refusal"]("alpha/code has unpushed commits: " + "c" * 40, 65)
        return helper(arguments, supplied)

    monkeypatch.setattr(following.host, "follow_project_command", held)
    answer = follow(following, "b")
    assert answer["projects"][0]["state"] == "held" and "c" * 40 in answer["projects"][0]["why"]
    assert following.host.records()["bob"]["locked"]
    assert not [room for room in rooms if room[0] == "drop-room"]
    monkeypatch.setattr(following.host, "follow_project_command", helper)
    assert follow(following)["projects"] == []
    assert rooms[-1] == ("drop-room", "alpha", [])
    assert not following.host.path("/etc/porelo-host/projects/alpha.conf").exists()


@pytest.mark.parametrize("code", [75, 78])
@pytest.mark.parametrize("verb", ["keep-room", "drop-room"])
def test_room_failures_retry_only_transient_failures(following, monkeypatch, code, verb):
    """Prevent losing a pending room deletion or repeatedly changing a room the gate does not own."""
    unused, rooms = project_services(following, monkeypatch, forge=False)
    if verb == "drop-room":
        follow(following)
        following.reply["projects"] = []

    def unavailable(action, name, persons):
        rooms.append((action, name, persons))
        raise following.scope["Refusal"]("gate refused", code)

    monkeypatch.setattr(following.host, "follow_room_command", unavailable)
    answer = follow(following, "b")
    assert str(code) in answer["projects"][0]["why"]
    count = len(rooms)
    follow(following)
    assert len(rooms) == count + (code == 75)


@pytest.mark.parametrize("damage", ["members", "keys", "duplicate", "entry", "name"])
def test_a_bad_project_cannot_stop_another_projects_revocations(following, monkeypatch, damage):
    """Prevent one malformed project from keeping an unrelated removed member's account and ACL active."""
    project_services(following, monkeypatch, forge=False, gate=False)
    follow(following)
    beta = copy.deepcopy(following.reply["projects"][0])
    beta["project"] = "beta"
    beta["members"] = [{"login": "alice", "role": "admin", "locked": False}]
    if damage == "members":
        beta["members"][0]["locked"] = "false"
    elif damage == "keys":
        beta["signing_keys"] = [None]
    elif damage == "name":
        beta["project"] = ["beta"]
    elif damage == "entry":
        beta = None
    following.reply["projects"] = [beta, copy.deepcopy(beta)] if damage == "duplicate" else [beta]
    follow(following, "b")
    assert following.host.records()["bob"]["locked"]
    assert not following.host.path("/etc/porelo-host/organization/projects/alpha.json").exists()


def test_a_room_loses_a_locked_member_on_the_same_follow(following, monkeypatch):
    """Prevent a project lock from leaving the removed person reading the project's conversation."""
    unused, rooms = project_services(following, monkeypatch, forge=False)
    follow(following)
    following.reply["projects"][0]["members"][1]["locked"] = True
    follow(following, "b")
    assert rooms[-1] == ("keep-room", "alpha", ["bob"])


def test_the_root_project_child_inherits_the_lock_and_receives_the_token_only_on_stdin(following, monkeypatch):
    """Prevent a child deadlock or a central credential escaping through a command argument or diagnostic."""
    host = following.host
    path = host.path("/usr/local/sbin/porelo-host-project")
    host.write(path, "#!/usr/bin/python3\n", 0o755)
    observed = []
    secret = "central-fixture-private-token"

    def child(arguments, input=None, **kwargs):
        observed.append((arguments, input, kwargs))
        return subprocess.CompletedProcess(arguments, 69, secret, secret)

    monkeypatch.setattr(host, "runner", child)
    with host.path("/etc/porelo-host/forge.conf").open("rb") as lock:
        host.project_lock_fd = lock.fileno()
        with pytest.raises(following.scope["Refusal"]) as failure:
            host.follow_project_command(
                ["migrate", "alpha"], {"address": "git@example.org:acme/alpha.git", "token": secret}
            )
        assert secret not in str(failure.value)
        arguments, supplied, options = observed[0]
        assert arguments[-2:] == ["--lock-fd", str(lock.fileno())]
        assert options["pass_fds"] == (lock.fileno(),)
        assert json.loads(supplied)["token"] == secret and secret not in str(arguments)


def helper_answering(following, monkeypatch, code, stdout, stderr):
    """Stand in for the installed root helper's process alone, so its output reaches the real reading of it."""
    host = following.host
    host.write(host.path("/usr/local/sbin/porelo-host-project"), "#!/usr/bin/python3\n", 0o755)
    monkeypatch.setattr(
        host, "runner", lambda arguments, **kwargs: subprocess.CompletedProcess(arguments, code, stdout, stderr)
    )
    return host.path("/etc/porelo-host/forge.conf").open("rb")


def refused_words(following, supplied=None):
    host = following.host
    with pytest.raises(following.scope["Refusal"]) as failure:
        host.follow_project_command(["migrate", "alpha"], supplied)
    return failure.value


def test_a_helpers_refusal_is_given_in_its_own_words_with_its_exit(following, monkeypatch, capsys):
    """Prevent a person being told only that a helper exited, with the reason lost in a captured stream."""
    words = "the central forge refused the deploy-key request (HTTP 403)"
    other = "a line before it\n"
    with helper_answering(following, monkeypatch, 65, "", f"{other}porelo-host-project: {words}\n") as lock:
        following.host.project_lock_fd = lock.fileno()
        error = refused_words(following)
    assert error.shown() == f"{words} (exit 65)"
    assert error.code == 69, "a helper's 65 or 78 must not read as the follow's held or refused room"
    journal = capsys.readouterr().err
    assert words in journal and other.strip() not in journal


@pytest.mark.parametrize(
    "stderr",
    [
        "central-fixture-private-token\nporelo-host-project: the forge refused\n",
        "porelo-host-project: the forge said central-fixture-private-token\n",
        "porelo-host-project: the forge said central-fixture\x07-private-token\n",
        "Traceback (most recent call last):\nValueError: central-fixture-private-token\n",
        "central-fixture-private-token",
        "",
    ],
)
def test_no_token_in_a_helpers_output_reaches_why_or_the_journal(following, monkeypatch, capsys, stderr):
    """Prevent the central token reaching status or a journal through a helper's diagnostic."""
    token = "central-fixture-private-token"
    with helper_answering(following, monkeypatch, 65, "", stderr) as lock:
        following.host.project_lock_fd = lock.fileno()
        error = refused_words(following, {"address": "git@example.org:acme/alpha.git", "token": token})
    assert token not in error.shown() and token not in capsys.readouterr().err
    if "the forge refused" in stderr:
        assert error.shown() == "the forge refused (exit 65)"
    else:
        assert error.shown() == "the project helper migrate exited 65 (exit 69)"


def test_a_last_line_not_the_helpers_own_is_never_given(following, monkeypatch, capsys):
    """Prevent a crash's last line, which may repeat any credential the process held, reaching status or the journal."""
    with helper_answering(following, monkeypatch, 1, "", "Traceback:\nValueError: an-admin-credential\n") as lock:
        following.host.project_lock_fd = lock.fileno()
        error = refused_words(following)
    assert "credential" not in error.shown() + capsys.readouterr().err
    assert error.shown() == "the project helper migrate exited 1 (exit 69)"


def test_a_helpers_words_are_bounded_and_carry_no_control_characters(following, monkeypatch):
    """Prevent a helper's line forging a status line or a journal entry of its own."""
    with helper_answering(following, monkeypatch, 65, "", "porelo-host-project: a\x1b[31m\tb" + "c" * 900) as lock:
        following.host.project_lock_fd = lock.fileno()
        shown = refused_words(following).shown()
    assert len(shown) < 330 and all(char.isprintable() for char in shown)


def test_off_says_in_the_journal_which_key_stays_at_the_central_forge(following, monkeypatch, capsys):
    """Prevent a host's deploy key staying able to read with nobody told it is there."""
    answer = {
        "project": "alpha",
        "removed": True,
        "left_at_central": [{"address": "git@example.org:acme/alpha.git", "title": "porelo host\x1b build"}],
    }
    with helper_answering(following, monkeypatch, 0, json.dumps(answer), "") as lock:
        following.host.project_lock_fd = lock.fileno()
        following.host.follow_project_command(["remove", "alpha"])
    journal = capsys.readouterr().err
    assert "git@example.org:acme/alpha.git" in journal and "porelo host build" in journal.replace("\x1b", "")
    assert "\x1b" not in journal and "stays" in journal


def status_why(host):
    return next(item for item in host.org_status("host")["projects"] if item["project"] == "alpha")


def test_a_refused_migrations_why_lasts_until_a_later_try_ends(following, monkeypatch):
    """Prevent the reason of a refusal vanishing within minutes while its project still waits for a token."""
    project_services(following, monkeypatch, gate=False)
    host = following.host
    follow(following)
    original = host.follow_project_command
    answers = iter(["the first refusal", "the second refusal", None])

    def refusing(arguments, supplied=None):
        if arguments[0] != "migrate":
            return original(arguments, supplied)
        words = next(answers)
        if words:
            raise following.scope["Refusal"](words, 69)
        return {}

    monkeypatch.setattr(host, "follow_project_command", refusing)
    token = b"central-fixture-private-token\n"
    with contextlib.suppress(following.scope["Refusal"]):
        host.execute(["org", "refresh"], token)
    assert "the first refusal" in status_why(host)["why"]
    follow(following)
    follow(following)
    held = status_why(host)
    assert held["state"] == "waiting-for-token" and "the first refusal" in held["why"]
    with contextlib.suppress(following.scope["Refusal"]):
        host.execute(["org", "refresh"], token)
    assert "the second refusal" in status_why(host)["why"] and "first" not in status_why(host)["why"]
    with contextlib.suppress(following.scope["Refusal"]):
        host.execute(["org", "refresh"], token)
    carried = status_why(host)
    assert carried["state"] == "carried" and "refusal" not in str(carried["why"])


def test_a_removal_refused_for_another_reason_than_commits_gives_its_words_and_stays_held(
    following, monkeypatch, capsys
):
    """Prevent a person being told only that no comparison was made, when the helper said what stands in the way."""
    words = "the forge has no organization for registered project alpha"
    stderr = f"porelo-host-project: {words}\n"
    with helper_answering(following, monkeypatch, 65, '{"project": "alpha", "unpushed": {}}', stderr) as lock:
        following.host.project_lock_fd = lock.fileno()
        with pytest.raises(following.scope["Refusal"]) as failure:
            following.host.follow_project_command(["remove", "alpha"])
    assert failure.value.code == 65, "the follow reads 65 as a project still held"
    assert failure.value.shown() == f"{words} (exit 65)"
    assert words in capsys.readouterr().err


def test_a_project_put_on_again_is_migrated_though_its_record_outlived_the_removal(following, monkeypatch):
    """Prevent an empty forge organization standing as carried, when a refused room kept the old progress record."""
    actions, unused = project_services(following, monkeypatch)
    host = following.host
    named = following.reply["projects"]
    follow(following)
    host.execute(["org", "refresh"], b"central-fixture-private-token\n")
    original = host.follow_room_command

    def no_drop(action, name, persons):
        if action == "drop-room":
            raise following.scope["Refusal"]("gate away", 75)
        return original(action, name, persons)

    monkeypatch.setattr(host, "follow_room_command", no_drop)
    following.reply["projects"] = []
    with contextlib.suppress(following.scope["Refusal"]):
        follow(following)
    assert not host.path("/etc/porelo-host/projects/alpha.conf").exists()
    assert "alpha" in host.host_projects(), "the room's retry must keep the record"
    monkeypatch.setattr(host, "follow_room_command", original)
    following.reply["projects"] = named
    actions.clear()
    # Losing the project locked its members and their forge logins have no stand-in here; their return is not held here.
    monkeypatch.setattr(host, "follow_project_admin", lambda project, records: ("bob", "ssh-ed25519 fixture"))
    with contextlib.suppress(following.scope["Refusal"]):
        follow(following)
    assert status_why(host)["state"] == "waiting-for-token"
    with contextlib.suppress(following.scope["Refusal"]):
        host.execute(["org", "refresh"], b"central-fixture-private-token\n")
    assert [args[0] for args, unused in actions] == ["add", "migrate"]


def status_why_after_follow(following):
    follow(following)
    return status_why(following.host)


def test_a_kept_refusal_hides_nothing_the_organization_says_now_and_ends_with_the_forge(following, monkeypatch):
    """Prevent an old refusal hiding a newer reason, or standing on a project no forge will try again."""
    project_services(following, monkeypatch, gate=False)
    host = following.host
    follow(following)
    original = host.follow_project_command

    def refusing(arguments, supplied=None):
        if arguments[0] == "migrate":
            raise following.scope["Refusal"]("the first refusal", 69)
        return original(arguments, supplied)

    monkeypatch.setattr(host, "follow_project_command", refusing)
    with contextlib.suppress(following.scope["Refusal"]):
        host.execute(["org", "refresh"], b"central-fixture-private-token\n")
    following.reply["projects"][0]["address"] = "has spaces"
    why = status_why_after_follow(following)["why"]
    assert "the first refusal" in why and "unusable address" in why
    following.reply["projects"][0]["address"] = "git@example.org:acme/alpha.git"
    monkeypatch.setattr(host, "forge_configuration", lambda user: None)
    carried = status_why_after_follow(following)
    assert carried["state"] == "carried" and "the first refusal" not in str(carried["why"])


def test_a_passing_room_refusal_does_not_last_like_a_migrations(following, monkeypatch):
    """Prevent a healed fault standing in status for good, which would hide the state a person must act on."""
    unused, rooms = project_services(following, monkeypatch)
    host = following.host
    follow(following)
    original = host.follow_room_command

    def gate_away(*unused):
        raise following.scope["Refusal"]("gate away", 75)

    monkeypatch.setattr(host, "follow_room_command", gate_away)
    follow(following)
    assert "gate away" in status_why(host)["why"]
    monkeypatch.setattr(host, "follow_room_command", original)
    follow(following)
    assert "gate away" not in str(status_why(host)["why"])


@pytest.mark.parametrize("code", [0, 75, 78])
def test_room_commands_run_as_the_gate_account_with_credentials_on_stdin(following, monkeypatch, code):
    """Prevent root owning a gate room or disclosing the gate's admin credential in an argument or error."""
    host = following.host
    host.commands.update({"cat", following.scope["TRANSPORT"]})
    secret = "matrix-fixture-admin-token"
    monkeypatch.setattr(host, "matrix_admin_token", lambda: secret)
    seen = []

    def command(arguments, input=None):
        seen.append((arguments, input))
        return subprocess.CompletedProcess(
            arguments,
            code,
            json.dumps({"homeserver": "unix:/run/porelo-matrix/client.sock", "room": "#alpha:matrix.example.org"}),
            secret,
        )

    monkeypatch.setattr(host, "runner", command)
    if code:
        with pytest.raises(following.scope["Refusal"]) as failure:
            host.follow_room_command("keep-room", "alpha", ["bob", "charlie"])
        assert failure.value.code == code and secret not in str(failure.value)
    else:
        assert host.follow_room_command("keep-room", "alpha", ["bob", "charlie"])["room"] == "#alpha:matrix.example.org"
    arguments, supplied = seen[0]
    assert arguments[:4] == ["runuser", "-u", "porelo-matrix", "--"]
    assert arguments[-5:] == ["keep-room", "--project", "alpha", "--persons", "bob,charlie"]
    assert json.loads(supplied) == {"secrets": {"PORELO_MATRIX_ADMIN_TOKEN": secret}}
    assert secret not in str(arguments)


def test_refresh_can_put_on_a_project_before_the_timer_has_seen_it(following, monkeypatch):
    """Prevent carry followed immediately by refresh from rejecting the only migration token."""
    actions, unused = project_services(following, monkeypatch, gate=False)
    answer = following.host.execute(["org", "refresh"], b"central-fixture-private-token\n")
    assert answer["projects"][0]["state"] == "carried"
    assert [args[0] for args, unused in actions] == ["add", "migrate"]


def test_a_removed_gate_is_not_called_for_a_departing_project(following, monkeypatch):
    """Prevent a host without its gate from attempting to manage a room through a different service."""
    unused, rooms = project_services(following, monkeypatch, forge=False)
    follow(following)
    following.host.path("/etc/systemd/system/porelo-matrix-gate.socket").unlink()
    following.reply["projects"] = []
    follow(following, "b")
    assert [verb for verb, _name, _persons in rooms] == ["keep-room"]


def test_signers_for_a_valid_project_never_receive_an_unusable_project_entry(following, monkeypatch):
    """Prevent a malformed neighboring project from stripping a valid project's allowed signers."""
    host = following.host
    isolated = host.isolated_porelo

    def checked(unit, staged, arguments, *args, **kwargs):
        if unit == "porelo-host-org-signers":
            value = json.loads(staged["state"].read_text())
            assert all(isinstance(item, dict) and item.get("project") == "alpha" for item in value["projects"])
        return isolated(unit, staged, arguments, *args, **kwargs)

    monkeypatch.setattr(host, "isolated_porelo", checked)
    following.reply["projects"].append(None)
    follow(following)
    assert host.path("/etc/porelo-host/signers/alpha.certifiers").read_text()


def test_an_expired_project_signing_key_cannot_register_a_forge_project(following, monkeypatch):
    """Prevent an expired signing authority from being pinned during a new project's registration."""
    actions, unused = project_services(following, monkeypatch, gate=False)
    following.reply["projects"][0]["signing_keys"][0]["valid_until"] = "2026-11-03"
    answer = follow(following)
    assert not actions
    assert "no unlocked admin with a current signing key" in answer["projects"][0]["why"]


def test_a_held_project_revokes_its_room_members_before_its_forge_can_go(following, monkeypatch):
    """Prevent a departed member who still has another membership from reading a held project's room."""
    actions, rooms = project_services(following, monkeypatch)
    beta = copy.deepcopy(following.reply["projects"][0])
    beta["project"] = "beta"
    beta["members"] = [{"login": "bob", "role": "admin", "locked": False}]
    following.reply["projects"].append(beta)
    follow(following)
    following.reply["projects"] = [beta]
    helper = following.host.follow_project_command

    def held(arguments, supplied=None):
        if arguments == ["remove", "alpha"]:
            raise following.scope["Refusal"]("unpushed work", 65)
        return helper(arguments, supplied)

    monkeypatch.setattr(following.host, "follow_project_command", held)
    follow(following, "b")
    assert not following.host.records()["bob"]["locked"]
    assert ("keep-room", "alpha", []) in rooms
    assert not [verb for verb, name, _persons in rooms if name == "alpha" and verb == "drop-room"]


def migrated_project(state, monkeypatch, stdout='{"project":"alpha","repositories":[]}', code=0):
    """A project on the host's forge, migrated, with the helper's central answer stood in."""
    project_services(state, monkeypatch, gate=False)
    host = state.host
    calls = []
    helper = host.path("/usr/local/sbin/porelo-host-project")
    helper.parent.mkdir(parents=True, exist_ok=True)
    host.write(helper, "#!/bin/true\n", 0o755)

    def runner(arguments, **kwargs):
        if len(arguments) > 1 and arguments[1] == "central-state":
            calls.append(arguments[:3])
            if isinstance(stdout, Exception):
                raise stdout
            return subprocess.CompletedProcess(arguments, code, stdout, "")
        return original(arguments, **kwargs)

    original = host.runner
    host.runner = runner
    follow(state)
    host.execute(["org", "refresh"], b"central-fixture-private-token\n")
    return calls


def central_answer(state):
    return json.loads(state.host.path("/etc/porelo-host/organization/central/alpha.json").read_text())


ROWS = [
    {"repository": "a", "state": "ahead", "commits": 3},
    {"repository": "b", "state": "up-to-date"},
    {"repository": "c", "state": "moved-on"},
    {"repository": "d", "state": "cannot-say", "why": "no-read-key"},
]


def test_how_main_stands_is_published_to_the_projects_unlocked_members_alone(following, monkeypatch):
    """Prevent a nonmember reading a project's state, or a locked member keeping sight of it."""
    state = following
    stdout = json.dumps({"project": "alpha", "repositories": ROWS})
    calls = migrated_project(state, monkeypatch, stdout)
    assert calls and calls[-1][1:] == ["central-state", "alpha"]
    answer = central_answer(state)
    assert answer == {"project": "alpha", "read_at": "2026-11-03T00:00:00Z", "repositories": ROWS}
    path = state.host.path("/etc/porelo-host/organization/central/alpha.json")
    assert readers(state, path) == {1001, 1002} and path.stat().st_mode & 0o077 == 0
    state.reply["projects"][0]["members"][0]["locked"] = True
    follow(state, "b")
    assert readers(state, path) == {1002}


@pytest.mark.parametrize(
    "stdout, code",
    [
        ("", 69),
        ("not json", 0),
        (json.dumps({"project": "other", "repositories": ROWS}), 0),
        (json.dumps({"project": "alpha", "repositories": "none"}), 0),
        (json.dumps({"project": "alpha", "repositories": [{"repository": "a", "state": "fine"}]}), 0),
        (json.dumps({"project": "alpha", "repositories": [{"repository": "a", "state": "ahead", "commits": 0}]}), 0),
        (json.dumps({"project": "alpha", "repositories": [{"repository": "a", "state": "up-to-date", "why": "x"}]}), 0),
        (json.dumps({"project": "alpha", "repositories": [{"repository": "a/b", "state": "up-to-date"}]}), 0),
        (json.dumps({"project": "alpha", "repositories": [{"repository": "a", "state": "cannot-say", "why": "?"}]}), 0),
        (subprocess.TimeoutExpired("helper", 300), 0),
    ],
)
def test_a_helper_that_cannot_say_leaves_no_repository_and_does_not_fail_the_follow(following, monkeypatch, stdout, code):
    """Prevent a central forge out of reach stopping the follow, or a malformed answer reading as up to date."""
    state = following
    migrated_project(state, monkeypatch, stdout, code)
    assert central_answer(state)["repositories"] == []
    assert state.host.execute(["org", "follow"], b"")["refused"] is None


def test_a_project_not_copied_has_no_central_answer_and_one_taken_off_loses_it(following, monkeypatch):
    """Prevent a stale prompt outliving its project, and a project with no copy reading as an answer."""
    state = following
    path = state.host.path("/etc/porelo-host/organization/central/alpha.json")
    project_services(state, monkeypatch, gate=False)
    follow(state)
    assert not path.exists()
    migrated_project(state, monkeypatch)
    assert path.exists()
    state.reply["projects"] = []
    follow(state, "c")
    assert not path.exists()


def test_a_person_taken_out_loses_sight_of_the_answer_before_the_central_forge_is_asked(following, monkeypatch):
    """Prevent a slow or killed read leaving a removed member able to read the project's state."""
    state = following
    migrated_project(state, monkeypatch)
    path = state.host.path("/etc/porelo-host/organization/central/alpha.json")
    assert readers(state, path) == {1001, 1002}
    seen = []
    asking = state.host.runner

    def runner(arguments, **kwargs):
        if len(arguments) > 1 and arguments[1] == "central-state":
            seen.append(set(readers(state, path)))
        return asking(arguments, **kwargs)

    state.host.runner = runner
    state.reply["projects"][0]["members"][0]["locked"] = True
    follow(state, "b")
    assert seen == [{1002}]


def test_the_central_questions_of_one_follow_stay_within_a_budget(following, monkeypatch):
    """Prevent many unreachable projects using up the follow's own time limit before it publishes."""
    state = following
    migrated_project(state, monkeypatch)
    host = state.host
    second = copy.deepcopy(state.reply["projects"][0])
    second["project"] = "beta"
    state.reply["projects"].append(second)
    follow(state, "b")
    entries = json.loads(host.path("/etc/porelo-host/organization/host-projects.json").read_text())
    assert entries["alpha"]["migrated"]
    entries["beta"]["migrated"] = True
    host.write(host.path("/etc/porelo-host/organization/host-projects.json"), json.dumps(entries), 0o600)
    start = host.now()
    timeouts, asked = [], []
    asking = host.runner

    def runner(arguments, **kwargs):
        if len(arguments) > 1 and arguments[1] == "central-state":
            asked.append(arguments[2])
            timeouts.append(kwargs["timeout"])
            host.now = lambda: start + datetime.timedelta(seconds=kwargs["timeout"])
            raise subprocess.TimeoutExpired("helper", kwargs["timeout"])
        return asking(arguments, **kwargs)

    host.runner = runner
    follow(state, "c")
    assert asked == ["alpha"] and sum(timeouts) <= 120
    for name in ("alpha", "beta"):
        answer = json.loads(host.path(f"/etc/porelo-host/organization/central/{name}.json").read_text())
        assert answer["repositories"] == []


def test_a_repository_named_in_capitals_keeps_its_answer(following, monkeypatch):
    """Prevent a name the migration keeps from throwing away every repository's answer."""
    rows = [{"repository": "Code.Base", "state": "up-to-date"}]
    migrated_project(following, monkeypatch, json.dumps({"project": "alpha", "repositories": rows}))
    assert central_answer(following)["repositories"] == rows


def test_what_a_killed_write_left_among_the_answers_stops_no_later_follow(following, monkeypatch):
    """Prevent one interrupted follow leaving every later answer and its readers stale until someone cleans up."""
    state = following
    migrated_project(state, monkeypatch)
    directory = state.host.path("/etc/porelo-host/organization/central")
    left = directory / ".porelo-host-person.abc123"
    left.write_text("half\n")
    follow(state, "b")
    assert not left.exists()


def organization_admin(state, login, number, **changed):
    row = {
        "login": login,
        "key": ssh_key(number),
        "fingerprint": state.scope["fingerprint"](ssh_key(number)),
        "backup": False,
    }
    return {**row, **changed}


def pin_and_root(state):
    return (
        state.host.path("/etc/porelo-host/organization/pin").read_text(),
        state.host.path("/etc/ssh/authorized_keys/root").read_text(),
    )


def test_the_pin_holds_the_organization_admins_and_root_stays_with_the_machines(following):
    """Prevent a dismissed machine admin needing to confirm their replacement, or the role getting root unseen."""
    state = following
    state.reply["organization_admins"] = [organization_admin(state, "olivia", 7), organization_admin(state, "oscar", 8)]
    follow(state)
    pin, root = pin_and_root(state)
    assert pin == f"alice {ssh_key(1)}\nolivia {ssh_key(7)}\noscar {ssh_key(8)}\n"
    assert root == f"{ssh_key(1)}\n"
    assert not {"olivia", "oscar"} & set(state.host.records()), "the role makes no account"
    assert state.host.execute(["org", "status"], b"")["pinned"] == state.scope["fingerprint"](ssh_key(1))


def test_a_list_that_arrives_on_a_server_already_set_up_is_taken_by_the_follow(following):
    """Prevent a server already running staying outside the role until someone stands on it."""
    state = following
    follow(state)
    assert pin_and_root(state)[0] == f"alice {ssh_key(1)}\n"
    state.reply["organization_admins"] = [organization_admin(state, "olivia", 7)]
    follow(state, "b")
    assert pin_and_root(state) == (f"alice {ssh_key(1)}\nolivia {ssh_key(7)}\n", f"{ssh_key(1)}\n")


def test_a_build_with_no_list_keeps_todays_pin_and_an_empty_list_is_the_same(following):
    """Prevent an older Porelo, or a list emptied, leaving a removed admin's key in the pin."""
    state = following
    state.reply["organization_admins"] = [organization_admin(state, "olivia", 7)]
    follow(state)
    state.reply["organization_admins"] = []
    follow(state, "b")
    assert pin_and_root(state)[0] == f"alice {ssh_key(1)}\n"
    state.reply["organization_admins"] = [organization_admin(state, "olivia", 7)]
    follow(state, "c")
    del state.reply["organization_admins"]
    follow(state, "d")
    assert pin_and_root(state)[0] == f"alice {ssh_key(1)}\n"


def test_a_person_in_both_lists_stands_in_the_pin_once_with_root(following):
    """Prevent one key twice in the pin, which the pin's own reader and renewal refuse."""
    state = following
    state.reply["organization_admins"] = [organization_admin(state, "alice", 1)]
    follow(state)
    assert pin_and_root(state) == (f"alice {ssh_key(1)}\n", f"{ssh_key(1)}\n")


def test_a_machine_admin_replaced_leaves_root_and_the_pin_with_no_step_of_theirs(following):
    """Prevent a dismissed admin keeping root, or the role losing the pin, when the machine's admin changes."""
    state = following
    state.reply["organization_admins"] = [organization_admin(state, "olivia", 7)]
    follow(state)
    state.reply["admins"] = [organization_admin(state, "charlie", 3)]
    follow(state, "b")
    assert pin_and_root(state) == (f"charlie {ssh_key(3)}\nolivia {ssh_key(7)}\n", f"{ssh_key(3)}\n")


@pytest.mark.parametrize(
    "damage",
    [
        lambda state: "none",
        lambda state: ["olivia"],
        lambda state: [{**organization_admin(state, "olivia", 7), "login": "root"}],
        lambda state: [{**organization_admin(state, "olivia", 7), "login": "Not A Login"}],
        lambda state: [{**organization_admin(state, "olivia", 7), "key": "ssh-rsa AAAA"}],
        lambda state: [{**organization_admin(state, "olivia", 7), "fingerprint": "SHA256:other"}],
        lambda state: [{**organization_admin(state, "olivia", 7), "backup": "no"}],
        lambda state: [organization_admin(state, "olivia", 7), organization_admin(state, "oscar", 7)],
    ],
)
def test_a_malformed_list_changes_nothing(following, damage):
    """Prevent an unreadable answer widening the pin, or leaving a pin no later fetch could read."""
    state = following
    follow(state)
    before = pin_and_root(state)
    state.reply["organization_admins"] = damage(state)
    state.reply["revision"] = "b" * 40
    with pytest.raises(state.scope["Refusal"], match="organization admin"):
        state.host.execute(["org", "follow"], b"")
    assert pin_and_root(state) == before
