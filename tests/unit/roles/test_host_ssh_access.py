"""Prevent SSH admission bypasses, partial revocations and surviving tunnels."""

import os
import runpy
import stat
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def host(tmp_path):
    scope = runpy.run_path(str(ROOT / "roles/porelo/files/porelo-host-person"))
    host = scope["Host"]()
    host.root = tmp_path
    host.refusal = scope["Refusal"]
    host.owner, host.group = os.getuid(), os.getgid()
    host.account = lambda user: SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid())
    host.accounts = {"alice": 1001}
    host.runner = lambda args, **kwargs: subprocess.run(args, capture_output=True, text=True, **kwargs)
    host.commands = {"ssh-keygen", "loginctl", "systemctl", "usermod", "gpasswd"}
    return host


def public_key(tmp_path):
    key = tmp_path / "fixture"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True, capture_output=True)
    return key.with_suffix(".pub").read_text().rsplit(" ", 1)[0]


def test_registry_key_has_expiry_and_no_source_address(host, tmp_path):
    """Prevent expired cards or a writable home key file from granting access."""
    key = public_key(tmp_path)
    host.write_authorized_key("alice", key, "20300102030405Z")
    target = host.path("/etc/ssh/authorized_keys/alice")
    assert target.read_text() == f'expiry-time="20300102030405Z" {key}\n'
    assert stat.S_IMODE(target.stat().st_mode) == 0o644
    before = target.read_bytes()
    with pytest.raises(host.refusal, match="expiry"):
        host.write_authorized_key("alice", key, "20301302030405Z")
    assert target.read_bytes() == before


def test_runtime_directory_is_private_and_restored_at_boot(host):
    """Prevent another person from replacing the return socket, including after reboot."""
    host.admit_runtime("alice")
    directory = host.path("/run/porelo-host/people/alice")
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert directory.stat().st_uid == os.getuid()
    assert host.path("/etc/tmpfiles.d/porelo-person-alice.conf").read_text() == (
        "d /run/porelo-host/people/alice 0700 alice alice -\n"
    )
    host.remove_runtime("alice")
    assert not directory.exists()
    assert not host.path("/etc/tmpfiles.d/porelo-person-alice.conf").exists()


def test_krl_is_valid_empty_then_replaced_without_a_partial_target(host, tmp_path, monkeypatch):
    """Prevent broken or half-written KRLs from denying every key or missing a revocation."""
    key = public_key(tmp_path)
    target = host.path("/etc/ssh/porelo-revoked.krl")
    host.write_krl([])
    assert target.read_bytes().startswith(b"SSHKRL\n\x00")
    query = tmp_path / "query.pub"
    query.write_text(key + "\n")
    assert subprocess.run(["ssh-keygen", "-Q", "-f", str(target), str(query)], capture_output=True).returncode == 0
    previous = target.read_bytes()
    replace = os.replace
    observed = []

    def publish(source, destination):
        if destination == target:
            observed.append(target.read_bytes())
        replace(source, destination)

    monkeypatch.setattr(os, "replace", publish)
    host.write_krl([key])
    assert observed == [previous]
    assert subprocess.run(["ssh-keygen", "-Q", "-f", str(target), str(query)], capture_output=True).returncode == 1
    previous = target.read_bytes()
    with pytest.raises(host.refusal):
        host.write_krl(["invalid"])
    assert target.read_bytes() == previous


def test_lock_ends_sessions_and_user_manager_even_when_a_hook_refuses(host):
    """Prevent an open SSH tunnel surviving a lock whose service revocation failed."""
    calls = []
    host.command = lambda args, **kwargs: calls.append(args)
    host.hooks = {name: lambda user: None for name in ("forge_lock", "matrix_expel_revoke")}
    host.record = lambda *args: None

    def refuse_hook(user):
        raise host.refusal("service unavailable", 69)

    host.hooks["forge_lock"] = refuse_hook
    with pytest.raises(host.refusal, match="service unavailable"):
        host.lock("alice", {"locked": False, "laptops": []}, False)
    assert ["loginctl", "terminate-user", "alice"] in calls
    assert ["systemctl", "stop", "user@1001.service"] in calls


def test_registry_revocation_ends_every_affected_users_sessions(host, tmp_path):
    """Prevent a revoked card's open tunnel from surviving an atomic KRL update."""
    key = public_key(tmp_path)
    calls = []
    command = host.command

    def record(args, **kwargs):
        if args[0] == "ssh-keygen":
            return command(args, **kwargs)
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")

    host.command = record
    host.apply_ssh_revocations([key], ["alice"])
    assert host.path("/etc/ssh/porelo-revoked.krl").read_bytes().startswith(b"SSHKRL\n\x00")
    assert calls == [["loginctl", "terminate-user", "alice"], ["systemctl", "stop", "user@1001.service"]]
