"""Guard the privileged password change against selecting another person's login."""

import io
import os
import runpy
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "roles/forge/files/porelo-host-forge-password"


@pytest.fixture
def password_host(tmp_path, monkeypatch):
    namespace = runpy.run_path(str(SCRIPT), run_name="password_tests")
    scope = namespace["main"].__globals__
    conf = tmp_path / "forge.conf"
    conf.write_text("address=192.0.2.1\nport=3000\nperson=bob\naccount=porelo-forge\n")
    conf.chmod(0o644)
    people = tmp_path / "people"
    people.mkdir()
    record = people / "alice.conf"
    record.write_text("role=project-admin\nprojects=\nlocked=false\nlaptop=fixture\n")
    record.chmod(0o600)
    monkeypatch.setitem(scope, "CONF", str(conf))
    monkeypatch.setitem(scope, "PEOPLE", str(people))
    real_lstat = os.lstat
    wrong_owner = set()

    def lstat(path):
        actual = real_lstat(path)
        mode = actual.st_mode & ~0o022 if stat.S_ISDIR(actual.st_mode) else actual.st_mode
        return SimpleNamespace(st_mode=mode, st_uid=1001 if str(path) in wrong_owner else 0)

    monkeypatch.setattr(scope["os"], "lstat", lstat)
    monkeypatch.setattr(scope["os"], "geteuid", lambda: 0)
    monkeypatch.setattr(scope["sys"], "argv", [str(SCRIPT)])
    monkeypatch.setattr(scope["sys"], "stdin", SimpleNamespace(buffer=io.BytesIO(b"fixture-password\n")))
    monkeypatch.setenv("SUDO_USER", "alice")
    monkeypatch.setenv("SUDO_UID", "1001")
    # The helper intentionally clears the environment; keep that change local to this test.
    monkeypatch.setattr(scope["os"], "environ", dict(os.environ))
    changes = []
    monkeypatch.setitem(scope, "CA", str(conf))
    monkeypatch.setitem(scope, "admin_token", lambda account: "fixture-admin-token")
    monkeypatch.setitem(scope, "set_password", lambda *args: changes.append(args) or 200)
    return SimpleNamespace(scope=scope, conf=conf, record=record, changes=changes, wrong_owner=wrong_owner)


def test_sudo_cannot_set_another_persons_forge_password(password_host, capsys):
    """Prevent a person with the sudo rule from changing the configured host admin's password."""
    password_host.scope["main"]()
    assert password_host.changes[0][2] == "alice"
    assert "bob" not in capsys.readouterr().out


@pytest.mark.parametrize("record", ["locked", "missing", "link", "writable", "wrong-owner", "duplicate"])
def test_sudo_needs_a_trusted_unlocked_person_record(password_host, capsys, record):
    """Prevent missing, forged or locked records from authorizing a password change."""
    path = password_host.record
    if record == "locked":
        path.write_text("locked=true\n")
    elif record == "missing":
        path.unlink()
    elif record == "link":
        path.unlink()
        path.symlink_to(password_host.conf)
    elif record == "writable":
        path.chmod(0o666)
    elif record == "wrong-owner":
        password_host.wrong_owner.add(str(path))
    else:
        path.write_text("locked=false\nlocked=true\n")
    with pytest.raises(SystemExit) as error:
        password_host.scope["main"]()
    # The records say no to a person locked or never admitted; a record root cannot trust is something missing.
    assert error.value.code == (65 if record in ("locked", "missing", "duplicate") else 69)
    assert password_host.changes == []
    assert "fixture-password" not in capsys.readouterr().err


def test_a_call_without_root_is_something_missing(password_host, capsys):
    """Keep the exit code the other host helpers give a caller who is not root."""
    password_host.scope["os"].geteuid = lambda: 1000
    with pytest.raises(SystemExit) as error:
        password_host.scope["main"]()
    assert error.value.code == 69 and "root" in capsys.readouterr().err
    assert password_host.changes == []


def test_sudo_does_not_require_the_configured_person(password_host):
    """Prevent the legacy single-person setting from deciding a sudo caller's identity."""
    password_host.conf.write_text(password_host.conf.read_text().replace("person=bob\n", "person=invalid/ignored\n"))
    password_host.scope["main"]()
    assert password_host.changes[0][2] == "alice"


@pytest.mark.parametrize("sudo", [False, True])
def test_direct_root_keeps_the_configured_login(password_host, sudo):
    """Keep the administrative password change available without a people record."""
    if sudo:
        password_host.scope["os"].environ.update(SUDO_USER="root", SUDO_UID="0")
    else:
        password_host.scope["os"].environ.clear()
    password_host.record.unlink()
    password_host.scope["main"]()
    assert password_host.changes[0][2] == "bob"


@pytest.mark.parametrize("locked", [False, True], ids=["unlocked", "locked"])
def test_sudo_accepts_membership_records_and_refuses_locked_ones(password_host, capsys, locked):
    """Prevent replacing role= and projects= with member= lines from breaking or unlocking a password change."""
    state = "true" if locked else "false"
    password_host.record.write_text(f"member=hand\nmember=alpha project-admin\nlocked={state}\nlaptop=fixture\n")
    if locked:
        with pytest.raises(SystemExit) as error:
            password_host.scope["main"]()
        assert error.value.code == 65
        assert password_host.changes == []
        assert "fixture-password" not in capsys.readouterr().err
    else:
        password_host.scope["main"]()
        assert password_host.changes[0][2] == "alice"
