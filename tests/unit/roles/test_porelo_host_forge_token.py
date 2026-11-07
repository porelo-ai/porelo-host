"""Guard explicit preparation of the person's forge credential without real accounts or secrets."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
COMMAND = ROOT / "roles/porelo/files/porelo-host-forge-token"
LIBRARY = ROOT / "roles/porelo/files/porelo-host-forge-token.sh"


@pytest.fixture
def person(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    config = tmp_path / "forge.conf"
    config.write_text("name=forge.example.org\naccount=porelo-forge\n")
    config.chmod(0o644)
    library = tmp_path / "forge-token.sh"
    library.write_text(LIBRARY.read_text().replace("forge_owner=0", f"forge_owner={os.getuid()}"))
    command = tmp_path / "command"
    if COMMAND.exists():
        command.write_text(
            COMMAND.read_text()
            .replace("/etc/porelo-host/forge.conf", str(config))
            .replace("/usr/local/share/porelo-host-forge-token.sh", str(library))
            .replace("/usr/local/sbin/porelo-host-person", str(bin_dir / "porelo-host-person"))
            .replace("helper_owner=0", f"helper_owner={os.getuid()}")
        )
    stub = (
        f"#!{sys.executable}\n"
        "import hashlib, json, os, pathlib, sys\n"
        "home = pathlib.Path(os.environ['HOME'])\n"
        "name = pathlib.Path(sys.argv[0]).name\n"
        "token = hashlib.sha1(b'fixture person credential').hexdigest()\n"
        "assert all(token not in arg for arg in sys.argv), 'token in arguments'\n"
        "assert token not in repr(dict(os.environ)), 'token in environment'\n"
        "failure = os.environ.get('STUB_FAILURE', '')\n"
        "if name == 'sudo':\n"
        "    assert sys.argv[1:] == ['-n', str(home / 'bin/porelo-host-person'), 'forge-token']\n"
        "    assert sys.stdin.buffer.read() == b'', 'credential helper consumed caller input'\n"
        "    os.execv(sys.argv[2], sys.argv[2:])\n"
        "elif name == 'porelo-host-person':\n"
        "    assert sys.argv[1:] == ['forge-token']\n"
        "    (home / 'forge-called').touch()\n"
        "    if failure == 'forge': sys.exit(1)\n"
        "    if failure == 'empty': sys.exit(0)\n"
        "    if failure == 'malformed': print('unexpected answer'); sys.exit(0)\n"
        "    sys.stdout.write(token)\n"
        "elif name == 'porelo':\n"
        "    assert sys.argv[1:] == ['vault', 'put', 'forge.example.org.person']\n"
        "    run = os.environ.get('EXPECT_RUNTIME')\n"
        "    if run:\n"
        "        assert os.environ.get('XDG_RUNTIME_DIR') == run, 'the vault needs the session runtime'\n"
        "        assert os.environ.get('DBUS_SESSION_BUS_ADDRESS') == f'unix:path={run}/bus', 'the vault needs the bus'\n"
        "    value = sys.stdin.read()\n"
        "    assert value == token, 'vault did not receive the forge token on stdin'\n"
        "    if failure == 'vault':\n"
        "        print(value); print(value, file=sys.stderr); sys.exit(1)\n"
        "    (home / 'entry').write_text(json.dumps({'name': sys.argv[3],\n"
        "        'digest': hashlib.sha256(value.encode()).hexdigest()}))\n"
    )
    for name in ("sudo", "porelo-host-person", "porelo"):
        path = bin_dir / name
        path.write_text(stub)
        path.chmod(0o755)
    return tmp_path


def run(person, *args, failure=""):
    return subprocess.run(
        ["bash", str(person / "command"), *args],
        input="caller input must not reach sudo",
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
        env={
            "PATH": f"{person / 'bin'}:/usr/bin:/bin",
            "HOME": str(person),
            "STUB_FAILURE": failure,
            "EXPECT_RUNTIME": f"/run/user/{os.getuid()}",
            "local_token": "caller-controlled exported value",
        },
    )


def assert_no_leak(person, result):
    token = hashlib.sha1(b"fixture person credential").hexdigest()
    assert token not in result.stdout + result.stderr, "the token reached command output"
    assert all(
        token.encode() not in path.read_bytes() for path in person.rglob("*") if path.is_file()
    ), "the token reached a file"


def test_the_command_puts_the_persons_token_on_stdin_without_exposing_it(person):
    """Prevent git reads without a credential, or a token leaking through argv, environment, files or output."""
    result = run(person)
    assert result.returncode == 0, result.stderr
    assert result.stdout == result.stderr == "", "successful preparation must be silent"
    token = hashlib.sha1(b"fixture person credential").hexdigest()
    assert json.loads((person / "entry").read_text()) == {
        "name": "forge.example.org.person",
        "digest": hashlib.sha256(token.encode()).hexdigest(),
    }
    assert_no_leak(person, result)


@pytest.mark.parametrize("failure", ["forge", "empty", "malformed"])
def test_a_refused_or_invalid_forge_token_fails_loudly_before_the_vault(person, failure):
    """Prevent a refused admission or invalid forge answer from being treated as a usable credential."""
    result = run(person, failure=failure)
    assert result.returncode == 69, result.stderr
    assert "forge token" in result.stderr and result.stdout == ""
    assert not (person / "entry").exists()
    assert_no_leak(person, result)


def test_a_refused_vault_write_has_a_distinct_status_without_printing_its_input(person):
    """Prevent a vault refusal from being confused with issuance failure or exposing its input in diagnostics."""
    result = run(person, failure="vault")
    assert result.returncode == 65, result.stderr
    assert "vault" in result.stderr and result.stdout == ""
    assert not (person / "entry").exists()
    assert_no_leak(person, result)


def test_a_refused_vault_write_leaves_the_new_token_to_its_caller(person):
    """Prevent a push going on after a closed vault with no token for the forge, since the old one is gone."""
    script = (
        f"source {person / 'forge-token.sh'}\n"
        f"refresh_person_forge_token {person / 'forge.conf'} {person / 'bin/porelo-host-person'}\n"
        "status=$?\n"
        "[[ $local_token =~ ^[0-9a-f]{40}$ ]] && echo kept\n"
        "exit $status\n"
    )
    result = subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
        env={"PATH": f"{person / 'bin'}:/usr/bin:/bin", "HOME": str(person), "STUB_FAILURE": "vault"},
    )
    assert result.returncode == 65, result.stderr
    assert result.stdout == "kept\n", "the token the forge made anew is what the caller pushes with"


@pytest.mark.parametrize(
    "case",
    ["missing", "symlink", "writable", "other-owner", "two-accounts", "bad-account", "no-name", "bad-name"],
)
def test_forge_settings_that_cannot_be_trusted_stop_before_any_token(person, case):
    """Prevent settings someone else can change, or that name no single forge, from choosing what the token goes to."""
    config = person / "forge.conf"
    if case == "missing":
        config.unlink()
    elif case == "symlink":
        target = person / "elsewhere.conf"
        target.write_text(config.read_text())
        config.unlink()
        config.symlink_to(target)
    elif case == "writable":
        config.chmod(0o666)
    elif case == "other-owner":
        library = person / "forge-token.sh"
        library.write_text(library.read_text().replace(f"forge_owner={os.getuid()}", f"forge_owner={os.getuid() + 1}"))
    else:
        config.write_text(
            {
                "two-accounts": "name=forge.example.org\naccount=porelo-forge\naccount=other\n",
                "bad-account": "name=forge.example.org\naccount=Bad Account\n",
                "no-name": "account=porelo-forge\n",
                "bad-name": "name=../forge\naccount=porelo-forge\n",
            }[case]
        )
    result = run(person)
    assert result.returncode == 69, result.stderr
    assert "forge settings" in result.stderr and result.stdout == ""
    assert not (person / "forge-called").exists()
    assert not (person / "entry").exists()


@pytest.mark.parametrize("case", ["missing", "symlink", "writable", "writable-directory"])
def test_a_helper_root_alone_cannot_change_is_never_sourced(person, case):
    """Prevent code another account can change from running with the person's open vault."""
    library = person / "forge-token.sh"
    if case == "missing":
        library.unlink()
    elif case == "symlink":
        target = person / "elsewhere.sh"
        target.write_text(library.read_text())
        library.unlink()
        library.symlink_to(target)
    elif case == "writable":
        library.chmod(0o666)
    else:
        person.chmod(0o777)
    try:
        result = run(person)
    finally:
        person.chmod(0o700)
    assert result.returncode == 69, result.stderr
    assert "helper" in result.stderr and result.stdout == ""
    assert not (person / "forge-called").exists()


@pytest.mark.parametrize("settings", [None, "host=stand-in\naccount=\n"])
def test_optional_preparation_does_nothing_on_a_host_without_a_forge(person, settings):
    """Prevent tools for hosts without a forge from requesting a nonexistent person's forge token."""
    config = person / "forge.conf"
    if settings is None:
        config.unlink()
    else:
        config.write_text(settings)
    result = run(person, "--if-forge")
    assert result.returncode == 0, result.stderr
    assert result.stdout == result.stderr == ""
    assert not (person / "forge-called").exists()
    assert not (person / "entry").exists()


def test_invalid_arguments_do_not_rotate_the_persons_token(person):
    """Prevent an unintended invocation from revoking the person's current credential."""
    result = run(person, "unexpected")
    assert result.returncode == 64 and result.stderr
    assert not (person / "forge-called").exists()


def test_installation_delivers_the_command_and_library_as_root_owned_files():
    """Prevent a missing or writable sourced helper from breaking preparation or executing another user's code."""
    tasks = yaml.safe_load((ROOT / "roles/porelo/tasks/install.yml").read_text())
    copies = [task["ansible.builtin.copy"] for task in tasks if "ansible.builtin.copy" in task]
    for name, destination, mode in (
        (COMMAND.name, "/usr/local/bin/porelo-host-forge-token", "0755"),
        (LIBRARY.name, "/usr/local/share/porelo-host-forge-token.sh", "0644"),
    ):
        matching = [copy for copy in copies if copy.get("dest") == destination]
        assert len(matching) == 1, f"expected one installation of {destination}, got {matching}"
        assert matching[0] == {
            "src": "{{ role_path }}/files/" + name,
            "dest": destination,
            "owner": "root",
            "group": "root",
            "mode": mode,
        }
