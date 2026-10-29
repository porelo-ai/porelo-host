"""porelo's own side of bring and join, run by the real ansible-playbook against a stand-in porelo in a scratch home."""

import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

HERE = Path(__file__).parent
PROJECT = "acme"
KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl"

PORELO = """#!/bin/bash
# Records each call and answers as Porelo would for a machine file whose project is in the setup directory.
printf '%s\\n' "$*" >> "$PORELO_LOG"
case "$1 $2" in
    "setup "*) echo "daemon   running" ;;
    "vault status") exit "${PORELO_VAULT_STATUS:-0}" ;;
    "vault list") printf 'deploy-key\\n' ;;
    "project inventory") cat "$PORELO_INVENTORY" ;;
    "project following") echo '{"follows": []}' ;;
    "project verify")
        [ -z "${PORELO_VERIFY_REFUSES:-}" ] || { echo "porelo: not_signed" >&2; exit 65; }
        echo '{"project": "acme", "commit": "c1", "access_commit": "a1", "signers": []}' ;;
    "project follow") ;;
    *) echo "unexpected: $*" >&2; exit 99 ;;
esac
"""


@pytest.fixture
def home(tmp_path):
    """A home whose setup directory is the person's, with a real project bundle and a machine file naming it."""
    home = tmp_path / "home"
    setup = home / ".local/share/porelo-host/setup" / PROJECT
    setup.mkdir(parents=True)
    for d in [home / ".local", home / ".local/share", home / ".local/share/porelo-host", setup.parent]:
        d.chmod(0o755)
    setup.chmod(0o700)
    repository = tmp_path / "repository"
    subprocess.run(["git", "init", "-q", str(repository)], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@t",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "first",
        ],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repository), "bundle", "create", "-q", str(setup / "project.bundle"), "--all"], check=True
    )
    (setup / "access.bundle").write_bytes((setup / "project.bundle").read_bytes())
    machine = {
        "project": {"name": PROJECT, "url": str(setup / "project.bundle"), "signed_by": KEY},
        "keys": [{"name": "deploy-key", "path": "keys/deploy"}],
        "access": {"bundle": "access.bundle"},
        "forge": {"repositories": [{"name": "app", "url": "https://central.example/acme/app.git"}]},
    }
    (setup / "machine.yml").write_text(yaml.safe_dump(machine))
    for name in ["machine.yml", "project.bundle", "access.bundle"]:
        (setup / name).chmod(0o600)
    return home


def run(home, act="bring", **env):
    """Run the own side as the test's account, its home moved to the scratch one, porelo replaced by the stand-in."""
    setup = home / ".local/share/porelo-host/setup" / PROJECT
    bin_dir = home.parent / "bin"
    bin_dir.mkdir(exist_ok=True)
    (bin_dir / "porelo").write_text(PORELO)
    (bin_dir / "porelo").chmod(0o755)
    machine = yaml.safe_load((setup / "machine.yml").read_text())
    inventory = home.parent / "inventory.yml"
    inventory.write_text(
        yaml.safe_dump(
            {
                "all": {
                    "vars": {"porelo_inventory_version": 2},
                    "hosts": {
                        "localhost": {
                            "porelo_project": machine["project"],
                            "porelo_vault_keys": [{"name": "deploy-key", "path": "/x"}],
                        }
                    },
                }
            }
        )
    )
    log = home.parent / "porelo.log"
    done = subprocess.run(
        [
            "ansible-playbook",
            "-i",
            "localhost,",
            str(HERE / "plays" / "own.yml"),
            "-e",
            f"porelo_project={PROJECT}",
            "-e",
            f"porelo_own_act={act}",
            "-e",
            f"__porelo_own_home={home}",
        ],
        env=dict(
            os.environ,
            ANSIBLE_NOCOLOR="1",
            PATH=f"{bin_dir}:{os.environ['PATH']}",
            PORELO_LOG=str(log),
            PORELO_INVENTORY=str(inventory),
            **env,
        ),
        capture_output=True,
        text=True,
        check=False,
    )
    calls = log.read_text().splitlines() if log.exists() else []
    return done, calls


def test_a_bring_from_the_persons_own_setup_verifies_both_bundles_and_follows_the_project(home):
    done, calls = run(home)
    assert done.returncode == 0, done.stdout + done.stderr
    setup = home / ".local/share/porelo-host/setup" / PROJECT
    verify = next(c for c in calls if c.startswith("project verify"))
    assert f"--repository {setup}/project.bundle" in verify
    assert f"--access-repository {setup}/access.bundle" in verify
    assert f"--project {PROJECT}" in verify and f"--signed-by {KEY}" in verify
    assert f"project follow {PROJECT} {setup}/project.bundle --signed-by={KEY}" in calls
    assert not any("--unverified" in c for c in calls)


@pytest.mark.parametrize(
    "spoil, named",
    [
        (lambda s: (s / "machine.yml").chmod(0o644), "machine.yml: plain file"),
        (lambda s: s.chmod(0o750), f"{PROJECT}: directory"),
        (lambda s: s.parent.chmod(0o777), "setup: directory"),
        (lambda s: (s / "access.bundle").unlink(), "access.bundle: missing"),
        (
            lambda s: ((s / "project.bundle").unlink(), (s / "project.bundle").symlink_to(s / "access.bundle")),
            "project.bundle: link",
        ),
    ],
    ids=["file-readable-by-others", "directory-open-to-group", "ancestor-writable-by-others", "missing", "link"],
)
def test_a_setup_file_or_directory_not_the_persons_alone_is_refused_by_name_before_porelo_reads_it(home, spoil, named):
    spoil(home / ".local/share/porelo-host/setup" / PROJECT)
    done, calls = run(home)
    assert done.returncode != 0
    assert named in done.stdout, done.stdout
    assert calls == []


def test_a_shut_vault_stops_the_bring_naming_the_stop_that_opens_it(home):
    done, calls = run(home, PORELO_VAULT_STATUS="3")
    assert done.returncode != 0
    assert "porelo-host-stop --stdin vault" in done.stdout
    assert not any(c.startswith("project follow ") for c in calls)


def test_an_access_bundle_porelo_refuses_stops_the_bring_before_the_follow_with_porelos_words(home):
    done, calls = run(home, PORELO_VERIFY_REFUSES="yes")
    assert done.returncode != 0
    assert "not_signed" in done.stdout
    assert not any(c.startswith("project follow ") for c in calls)


def test_a_join_refuses_a_machine_file_with_a_forge_section(home):
    done, calls = run(home, act="join")
    assert done.returncode != 0
    assert "a join reads no forge section" in done.stdout
    assert not any(c.startswith("project follow ") for c in calls)


@pytest.mark.parametrize(
    "repositories",
    [
        [],
        [{"name": "app", "url": "https://user@central.example/acme/app.git"}],
        [{"name": "app", "url": "http://central.example/acme/app.git"}],
        [{"name": "app", "url": "https://central.example/a.git"}, {"name": "app", "url": "https://central.example/b"}],
        [{"name": "../app", "url": "https://central.example/acme/app.git"}],
        [{"name": "app", "url": "https://central.example/acme/app.git", "mirror": True}],
    ],
    ids=["empty", "user-in-url", "not-https", "duplicate-name", "bad-name", "extra-key"],
)
def test_a_bring_refuses_a_forge_section_it_cannot_use_naming_it(home, repositories):
    machine_file = home / ".local/share/porelo-host/setup" / PROJECT / "machine.yml"
    machine = yaml.safe_load(machine_file.read_text())
    machine["forge"] = {"repositories": repositories}
    machine_file.write_text(yaml.safe_dump(machine))
    done, calls = run(home)
    assert done.returncode != 0
    assert "forge: must hold repositories alone" in done.stdout
    assert json.dumps(repositories[0]["url"]) in done.stdout if repositories else True
    assert not any(c.startswith("project follow ") for c in calls)


@pytest.mark.parametrize(
    "access",
    [None, {"bundle": "../other/access.bundle"}, {"bundle": "project.bundle"}, {"repository": "https://x/y"}],
    ids=["none", "elsewhere", "the-project-bundle", "a-repository"],
)
def test_a_machine_file_naming_another_access_bundle_is_refused_by_name(home, access):
    machine_file = home / ".local/share/porelo-host/setup" / PROJECT / "machine.yml"
    machine = yaml.safe_load(machine_file.read_text())
    machine["access"] = access
    machine_file.write_text(yaml.safe_dump(machine))
    done, calls = run(home)
    assert done.returncode != 0
    assert "access: the machine file must name the bundle access.bundle" in done.stdout
    assert not any(c.startswith("project follow ") for c in calls)
