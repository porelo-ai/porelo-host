#!/usr/bin/python3 -I
"""The host following its organization on a real machine, through the stand-in's answers: each step says what it
asked, and the run ends naming every wrong answer, with nothing of the token in what it prints.
"""

import datetime
import json
import os
import subprocess
import sys
from pathlib import Path

HELPER = "/usr/local/sbin/porelo-host-person"
SHARED = Path("/usr/local/share/porelo-org-standin")
KEYS = Path("/root/verify-org")
ORG = Path("/etc/porelo-host/organization")
TOKEN = "molecule-central-token-" + os.urandom(8).hex()
ENVIRON = {key: value for key, value in os.environ.items() if key != "SUDO_USER"}


def run(*words, given=""):
    return subprocess.run(words, input=given, text=True, capture_output=True, check=False, env=ENVIRON, timeout=400)


WRONG = []


def check(fact, asked, seen=""):
    if fact:
        print("ok:", asked)
    else:
        WRONG.append(f"asked {asked}; got {seen}")


def helper(*words, given=""):
    done = run(HELPER, *words, given=given)
    check(done.returncode == 0, f"porelo-host-person {' '.join(words)} to answer 0", done.stdout + done.stderr)
    return done


def status():
    return json.loads(helper("org", "status").stdout)


def person(login):
    return next((item for item in status()["persons"] if item["login"] == login), {"login": login, "state": None})


def answer(revision, **wanted):
    done = run("/root/org-answer.py", revision * 40, json.dumps(wanted))
    check(done.returncode == 0, f"the stand-in's answer {revision}", done.stderr)


def can_read(login, path):
    return run("runuser", "-u", login, "--", "cat", "--", str(path)).returncode == 0


def reaches(login):
    done = run(
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=10",
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        "-i",
        str(KEYS / login),
        f"{login}@127.0.0.1",
        "id",
        "-un",
    )
    return done.returncode == 0 and done.stdout.strip() == login


def public(login):
    return " ".join((KEYS / f"{login}.pub").read_text(encoding="utf-8").split()[:2])


PROJECT = "follow-one"
ACCESS = ORG / "projects" / f"{PROJECT}.json"
ALLOWED = Path("/etc/porelo-host/signers") / f"{PROJECT}.allowed"
CERTIFIERS = Path("/etc/porelo-host/signers") / f"{PROJECT}.certifiers"
EVERYONE = ["hostadmin", "fa", "fb", "fc"]
BOTH = {"fa": "admin", "fb": "developer"}
ROLES = {"admin": "project-admin", "developer": "developer"}

# Before its token the host has fetched nothing, and says what it waits for.
run("systemctl", "stop", "porelo-host-follow.timer")
enabled = run("systemctl", "is-enabled", "porelo-host-follow.timer").stdout.strip()
check(enabled == "enabled", "the follow's timer to be enabled by up", enabled)
summary = json.loads(Path("/etc/porelo-host/host.json").read_text(encoding="utf-8"))
check(summary["organization_read_key"].startswith("ssh-ed25519 "), "the read key in the host's summary", summary)
check(status()["organization"] == "waiting-for-token", "org status to wait for the token", status())
answer("a", admins=["hostadmin"], persons=EVERYONE[:3], projects={PROJECT: BOTH})
helper("org", "follow")
check(status()["commit"] is None, "org follow without a token to take nothing", status())

# The token once: the read key added, the first state taken, as the isolated units run it.
helper("org", "refresh", given=TOKEN + "\n")
check(status()["commit"] == "a" * 40, "org refresh to take the first state", status())
check((ORG / "read/organization.added").exists(), "the read key to be recorded as added")
kept = Path("/var/lib/private/porelo-host-org-fetch/seen")
check(kept.read_text(encoding="utf-8").splitlines() == ["first"], "the fetch's state directory to last", kept)

# What the members got, and nobody else.
for login, role in BOTH.items():
    seen = person(login)
    check(
        seen["state"] == "active" and seen["projects"] == [{"project": PROJECT, "role": ROLES[role]}],
        f"{login} to be active as {role}",
        seen,
    )
    check(reaches(login), f"{login} to reach the host with their key")
    check(can_read(login, ACCESS), f"{login} to read the project's file")
check(not can_read("nobody", ACCESS), "nobody else to read the project's file")
for path in (ALLOWED, CERTIFIERS):
    mode = path.stat().st_mode & 0o777
    check(mode == 0o644 and public("fb") in path.read_text(encoding="utf-8"), f"{path} to name fb, readable", mode)
    check(can_read("porelo-forge", path), f"the forge's account to read {path}")

# Again, as the timer does: the kept state goes along, nothing changes.
before = ACCESS.read_text(encoding="utf-8")
started = run("systemctl", "start", "porelo-host-follow.service")
check(started.returncode == 0, "the timer's service to follow", started.stderr)
check(kept.read_text(encoding="utf-8").splitlines()[-1] == "a" * 40, "the follow to name the state it holds", kept)
check(ACCESS.read_text(encoding="utf-8") == before, "a follow of the same state to change nothing")

# On the host's forge: the follow put the project there, and the members' push configs are their own.
RECORD = Path("/etc/porelo-host/projects") / f"{PROJECT}.conf"
FORGE = RECORD.parent.parent / "forge.conf"


def project_state():
    return next((item for item in status()["projects"] if item["project"] == PROJECT), None)


if FORGE.exists():
    check(RECORD.exists(), "the follow to register the project", project_state())
    # Its central address is invented here, so its repository waits; the walk migrates a real one.
    check(project_state()["state"] == "waiting-for-token", "the repository to wait for the migration", project_state())
    done = helper("org", "follow")
    for login in BOTH:
        path = Path(f"/home/{login}/.config/porelo-host/push/{PROJECT}.conf")
        owner = path.stat().st_uid if path.exists() else None
        check(
            owner is not None and owner == int(run("id", "-u", login).stdout),
            f"{login}'s push config to be their own",
            [owner, done.stderr],
        )

# A state the host's keys did not sign: refused, shown to the admin, the state kept; a forge that says nothing is not.
(SHARED / "words").write_text("refused-state: an owner replaced a host admin's card\n", encoding="utf-8")
(SHARED / "exit").write_text("65\n", encoding="utf-8")
done = run(HELPER, "org", "follow")
check(done.returncode == 65, "a refused state to answer 65", done.stdout + done.stderr)
check(
    "refused-state" in str(status()["refused"]) and status()["commit"] == "a" * 40,
    "org status to show the refusal and keep the state",
    status(),
)

# Root's way past it.
pin = ORG / "pin"
old = pin.read_text(encoding="utf-8")
subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "", "-f", str(KEYS / "newadmin")], check=True)
done = helper("org", "renew-pin", given=f'hostadmin {public("newadmin")}\n')
check(pin.read_text(encoding="utf-8") == f'hostadmin {public("newadmin")}\n', "the pin to be replaced", pin)
check(json.loads(done.stdout)["refused"] is None, "the renewal to clear the refusal", done.stdout)
helper("org", "renew-pin", given=old)
(SHARED / "words").write_text("cannot-say: the forge is away\n", encoding="utf-8")
(SHARED / "exit").write_text("69\n", encoding="utf-8")
done = run(HELPER, "org", "follow")
check(done.returncode == 69 and status()["refused"] is None, "a forge saying nothing to be no refusal", status())

# A newcomer comes in with the next state.
answer(
    "b",
    admins=["hostadmin"],
    persons=EVERYONE,
    projects={PROJECT: {"fa": "admin", "fb": "developer", "fc": "developer"}},
)
helper("org", "follow")
check(person("fc")["state"] == "active" and reaches("fc"), "fc to come in", status())

# A revocation: the key on the KRL, the login stopped, no signature good.
answer(
    "c", admins=["hostadmin"], persons=EVERYONE, revoked=["fb"], projects={PROJECT: {"fa": "admin", "fc": "developer"}}
)
helper("org", "follow")
check(person("fb")["state"] == "locked", "revoked fb to be locked", person("fb"))
said = run("ssh-keygen", "-Qf", "/etc/ssh/porelo-revoked.krl", str(KEYS / "fb.pub")).stdout
check("REVOKED" in said, "fb's key to be on the KRL", said)
check(not reaches("fb") and reaches("fa"), "fb stopped at SSH and fa not")
check(not can_read("fb", ACCESS), "fb not to read the project's file")
check(public("fb") not in ALLOWED.read_text(encoding="utf-8"), "fb's key out of the allowed signers")

# A membership lost: locked with a day to go, and back when the state says so.
answer("d", admins=["hostadmin"], persons=EVERYONE, revoked=["fb"], projects={})
helper("org", "follow")
check(not RECORD.exists(), "the project taken off the host's forge", project_state())
check(not ACCESS.exists() and not ALLOWED.exists() and not CERTIFIERS.exists(), "nothing of the project to stay")
check(project_state() is None, "org status not to name the project", project_state())
seen = person("fa")
day = (datetime.date.today() + datetime.timedelta(days=7)).isoformat()
check(seen["state"] == "locked" and seen.get("purge_on") == day, f"fa locked until {day}", seen)
check(not reaches("fa"), "fa stopped at SSH with no membership left")
answer("e", admins=["hostadmin"], persons=EVERYONE, revoked=["fb"], projects={PROJECT: {"fa": "admin"}})
helper("org", "follow")
seen = person("fa")
check(seen["state"] == "active" and "purge_on" not in seen and reaches("fa"), "fa back with its membership", seen)

# What the act leaves is nothing of its persons, for the next one.
answer("f", admins=["hostadmin"], persons=["hostadmin"], projects={})
helper("org", "follow")
for login in ("fa", "fb", "fc"):
    helper("purge", login)
    check(person(login)["state"] == "purged", f"{login} to be purged", person(login))

journal = run("journalctl", "-b", "--no-pager").stdout
check(TOKEN not in journal, "the token to stay out of the journal")
check(run("systemctl", "start", "porelo-host-follow.timer").returncode == 0, "the timer started again")
sys.exit("; ".join(WRONG) if WRONG else 0)
