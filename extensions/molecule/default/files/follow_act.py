#!/usr/bin/python3 -I
"""The host following its organization on a real machine, through the stand-in's answers: each step says what it
asked, and the run ends naming every wrong answer, with nothing of the token in what it prints.
"""

import datetime
import json
import os
import re
import subprocess
import sys
import tempfile
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

    # What a repository's review means on the real forge. The file's value is put where the follow keeps it, as the
    # central repository and its signed file are the walk's: the repository is made here, on the forge alone.
    PROGRESS = ORG / "host-projects.json"
    account = "porelo-forge"
    uid = run("id", "-u", account).stdout.strip()
    socket = f"/run/user/{uid}/porelo-forge/http.sock"
    made = run(
        "runuser",
        "-u",
        account,
        "--",
        "env",
        "-C",
        "/",
        f"XDG_RUNTIME_DIR=/run/user/{uid}",
        "podman",
        "exec",
        "forgejo",
        "forgejo",
        "admin",
        "user",
        "generate-access-token",
        "--username",
        "porelo-admin",
        "--token-name",
        "follow-act",
        "--scopes",
        "all",
        "--raw",
    )
    forge_token = made.stdout.strip()
    check(made.returncode == 0 and forge_token, "a token for the act's forge calls", made.stderr)

    def forge(method, route, body=None):
        done = run(
            "curl",
            "-sS",
            "-K",
            "-",
            "--unix-socket",
            socket,
            "-X",
            method,
            "-H",
            "Content-Type: application/json",
            "-w",
            "\n%{http_code}",
            *(["-d", json.dumps(body)] if body is not None else []),
            f"http://localhost/api/v1/{route}",
            given=f'header = "Authorization: token {forge_token}"\n',
        )
        text, unused, code = done.stdout.rpartition("\n")
        return int(code or 0), json.loads(text) if text.strip().startswith(("{", "[")) else None

    def followed():
        # A repository made here has no central address, so its members' push configs say so; only that may fail.
        done = run(HELPER, "org", "follow")
        check(
            done.returncode == 0 or "no valid central address" in done.stderr,
            "the follow to reach the rules",
            done.stderr,
        )

    def in_force(review):
        entries = json.loads(PROGRESS.read_text(encoding="utf-8"))
        entries[PROJECT].update(
            migrated=True,
            state="carried",
            file={"commit": "1" * 40, "signers": "", "address": address, "review": review, "repositories": {}},
        )
        PROGRESS.write_text(json.dumps(entries), encoding="utf-8")
        followed()

    address = next(
        item
        for item in json.loads((SHARED / "answer.json").read_text(encoding="utf-8"))["projects"]
        if item["project"] == PROJECT
    )["address"]
    code_name = address.rstrip("/").rsplit("/", 1)[-1].rsplit(":", 1)[-1].removesuffix(".git")
    repository = f"repos/{PROJECT}/{code_name}"
    code, unused = forge(
        "POST", f"orgs/{PROJECT}/repos", {"name": code_name, "auto_init": True, "default_branch": "main"}
    )
    check(code == 201, "the act's repository on the forge", code)
    forge(
        "PATCH",
        repository,
        {
            "allow_fast_forward_only_merge": True,
            "allow_merge_commits": False,
            "allow_rebase": False,
            "allow_rebase_explicit": False,
            "allow_squash_merge": False,
        },
    )

    # The host's judge takes only signed commits, so the author signs as a person the project's signers name.
    checkout = tempfile.TemporaryDirectory(prefix="follow-act-")
    git_port = re.search(r"^git_port=(\d+)$", FORGE.read_text(encoding="utf-8"), re.M).group(1)

    def git(*words):
        return subprocess.run(
            [
                "git",
                "-C",
                checkout.name,
                "-c",
                "gpg.format=ssh",
                "-c",
                f"user.signingkey={KEYS / 'fa'}",
                "-c",
                "commit.gpgsign=true",
                "-c",
                "user.name=fa",
                "-c",
                "user.email=fa@example.org",
                *words,
            ],
            text=True,
            capture_output=True,
            check=False,
            timeout=120,
            env={
                **ENVIRON,
                "GIT_TERMINAL_PROMPT": "0",
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "http.extraHeader",
                "GIT_CONFIG_VALUE_0": f"Authorization: token {forge_token}",
            },
        )

    cloned = git("clone", "-q", f"http://127.0.0.1:{git_port}/{PROJECT}/{code_name}.git", ".")
    check(cloned.returncode == 0, "the act's repository to clone", cloned.stderr)

    def commit_on_main(name):
        for words in (("fetch", "-q", "origin", "main"), ("checkout", "-q", "-B", name, "origin/main")):
            git(*words)
        Path(checkout.name, f"{name}.txt").write_text(name, encoding="utf-8")
        git("add", ".")
        made = git("commit", "-q", "-m", name)
        check(made.returncode == 0, f"a signed commit for {name}", made.stderr)

    def merged_alone(branch):
        commit_on_main(branch)
        pushed = git("push", "-q", "origin", branch)
        check(pushed.returncode == 0, f"the judge to take the signed branch {branch}", pushed.stderr)
        code, pull = forge("POST", f"{repository}/pulls", {"head": branch, "base": "main", "title": branch})
        check(code == 201, f"a pull request from {branch}", [code, pull])
        if code != 201:
            return 0
        return forge("POST", f"{repository}/pulls/{pull['number']}/merge", {"Do": "fast-forward-only"})[0]

    in_force("optional")
    code, rule = forge("GET", f"{repository}/branch_protections/main")
    check(
        code == 200 and rule["required_approvals"] == 0 and rule["dismiss_stale_approvals"] is True,
        "optional to need no approval on the forge",
        [code, rule],
    )
    check(merged_alone("alone") == 200, "the author to merge their own when optional")
    commit_on_main("direct")
    check(git("push", "-q", "origin", "HEAD:main").returncode != 0, "no direct push to main when optional")
    in_force("required")
    code, rule = forge("GET", f"{repository}/branch_protections/main")
    check(code == 200 and rule["required_approvals"] == 1, "required to need an approval on the forge", [code, rule])
    check(400 <= merged_alone("waits") < 500, "the author not to merge alone when required")
    forge("PATCH", f"{repository}/branch_protections/main", {"required_approvals": 0, "dismiss_stale_approvals": False})
    followed()
    code, rule = forge("GET", f"{repository}/branch_protections/main")
    check(
        rule["required_approvals"] == 1 and rule["dismiss_stale_approvals"] is True,
        "a rule changed by hand to be set back",
        rule,
    )
    checkout.cleanup()
    check(forge("DELETE", repository)[0] == 204, "the act's repository removed")
    forge("DELETE", "users/porelo-admin/tokens/follow-act")
    entries = json.loads(PROGRESS.read_text(encoding="utf-8"))
    for done_key in ("migrated", "file", "file_refused", "taken", "repositories_why"):
        entries[PROJECT].pop(done_key, None)
    PROGRESS.write_text(json.dumps(entries), encoding="utf-8")

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
