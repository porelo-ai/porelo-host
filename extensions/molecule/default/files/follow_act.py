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

HELPER = "/usr/sbin/porelo-host"
SHARED = Path("/usr/local/share/porelo-org-standin")
KEYS = Path("/root/verify-org")
ORG = Path("/etc/porelo-host/organization")
TOKEN = "molecule-central-token-" + os.urandom(8).hex()
# Whether up gave the host its forge, as the scenario says: only a forge's hook reads a project's allowed signers.
if sys.argv[1:] not in (["on"], ["off"]):
    sys.exit(f"usage: follow_act.py on|off, not {sys.argv[1:]}")
FORGE_ON = sys.argv[1] == "on"
ENVIRON = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8"}


def run(*words, given=""):
    return subprocess.run(words, input=given, text=True, capture_output=True, check=False, env=ENVIRON, timeout=400)


WRONG = []


def check(fact, asked, seen=""):
    if fact:
        print("ok:", asked)
    else:
        WRONG.append(f"asked {asked}; got {seen}")


def helper(*words, given="", expected=0):
    done = run(HELPER, *words, given=given)
    check(done.returncode == expected, f"porelo-host {' '.join(words)} to answer {expected}", done.stdout + done.stderr)
    return done


def status():
    return json.loads(helper("org", "status", "--json").stdout)


def person(login):
    return next((item for item in status()["persons"] if item["login"] == login), {"login": login, "state": None})


def answer(revision, **wanted):
    done = run("/root/org-answer.py", revision * 40, json.dumps(wanted))
    check(done.returncode == 0, f"the stand-in's answer {revision}", done.stderr)


def matrix_account(login, username):
    """Register an account through the gate as the login, the way a person's client does, and answer its token."""
    body = {"username": username, "password": os.urandom(16).hex(), "auth": {"type": "m.login.dummy"}}
    done = run(
        "runuser", "-u", login, "--", "curl", "-sS", "--unix-socket", "/run/porelo-matrix/client.sock",
        "-X", "POST", "-H", "Content-Type: application/json", "-d", "@-",
        "http://localhost/_matrix/client/v3/register", given=json.dumps(body),
    )  # fmt: skip
    try:
        return json.loads(done.stdout)["access_token"]
    except (ValueError, KeyError):
        check(False, f"{login} to register {username} through the gate", done.stdout + done.stderr)
        return ""


def matrix_answers(access):
    """Ask the homeserver itself, as a purged person has no gate left, whether a token still acts: its HTTP code."""
    uid = run("id", "-u", "porelo-matrix").stdout.strip()
    done = run(
        "runuser", "-u", "porelo-matrix", "--", "curl", "-sS", "-o", "/dev/null", "-w", "%{http_code}", "-K", "-",
        "--unix-socket", f"/run/user/{uid}/porelo-matrix-gate/homeserver.sock",
        "http://localhost/_matrix/client/v3/account/whoami",
        given=f'header = "Authorization: Bearer {access}"\n',
    )  # fmt: skip
    return done.stdout.strip()


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
for path in (ALLOWED, CERTIFIERS) if FORGE_ON else (CERTIFIERS,):
    mode = path.stat().st_mode & 0o777
    check(mode == 0o644 and public("fb") in path.read_text(encoding="utf-8"), f"{path} to name fb, readable", mode)
    if FORGE_ON:
        check(can_read("porelo-forge", path), f"the forge's account to read {path}")
if not FORGE_ON:
    check(not ALLOWED.exists(), f"no {ALLOWED} without a forge to read it")

# Again, as the timer does: the kept state goes along, nothing changes.
before = ACCESS.read_text(encoding="utf-8")
started = run("systemctl", "start", "porelo-host-follow.service")
check(started.returncode == 0, "the timer's service to follow", started.stderr)
check(kept.read_text(encoding="utf-8").splitlines()[-1] == "a" * 40, "the follow to name the state it holds", kept)
check(ACCESS.read_text(encoding="utf-8") == before, "a follow of the same state to change nothing")

# A person has the host follow at once through their one sudo rule; anyone else is refused by sudo, before the program.
# A task's account, porelo-fb, is the forge's alone and no login here, so nobody stands for the one who is not a person.
asked = run("runuser", "-u", "fb", "--", "sudo", "-n", HELPER, "org", "follow-now")
check(asked.returncode == 0, "fb's org follow-now to end a pass", asked.stdout + asked.stderr)
check(status()["refused"] is None, "org status after fb's follow to name no refusal", status())
check(kept.read_text(encoding="utf-8").splitlines()[-1] == "a" * 40, "fb's follow to name the state it holds", kept)
check(ACCESS.read_text(encoding="utf-8") == before, "fb's follow of the same state to change nothing")
fetched = kept.read_text(encoding="utf-8")
refused = run("runuser", "-u", "nobody", "--", "sudo", "-n", HELPER, "org", "follow-now")
check(
    refused.returncode != 0 and refused.stderr.startswith("sudo:"),
    "sudo to refuse nobody's follow",
    refused.stderr,
)
check(kept.read_text(encoding="utf-8") == fetched, "nobody's refused follow to fetch nothing", kept)
widened = run("runuser", "-u", "fb", "--", "sudo", "-n", HELPER, "org", "follow-now", "--extra")
check(
    widened.returncode != 0 and widened.stderr.startswith("sudo:"),
    "sudo to refuse follow-now with an argument",
    widened.stderr,
)

# On the host's forge: the follow put the project there, and the members' push configs are their own.
RECORD = Path("/etc/porelo-host/projects") / f"{PROJECT}.conf"
FORGE = RECORD.parent.parent / "forge.conf"


def project_state():
    return next((item for item in status()["projects"] if item["project"] == PROJECT), None)


# The web gate serves the forge's own site alone: fa's browser creates a repository with a form, as a page of another
# site in that browser cannot.
OWN = ""
if FORGE_ON:
    SITE = dict(line.split("=", 1) for line in FORGE.read_text(encoding="utf-8").split())
    OWN = f"{SITE['name']}:{SITE['port']}"
    measured = run(
        "runuser",
        "-u",
        "fa",
        "--",
        HELPER,
        "forge",
        "measure",
        "--socket",
        "/run/porelo-forge/web.sock",
        "--host",
        OWN,
        "--requests",
        "8",
        "--concurrency",
        "2",
        "--per-connection",
        "2",
        "--path",
        "/api/v1/version",
    )
    check(measured.returncode == 0, "the native forge measure to serve eight requests", measured.stderr)
    if measured.returncode == 0:
        check(json.loads(measured.stdout)["failures"] == 0, "every measured gate request to succeed", measured.stdout)
# Gone with the act, also when it ends early.
GATE_JAR = tempfile.TemporaryDirectory(prefix="gate-act-")  # pylint: disable=consider-using-with
JAR = Path(GATE_JAR.name)
os.chown(JAR, int(run("id", "-u", "fa").stdout), -1)


def browser(method, route, headers=(), form=None, host=OWN):
    """A request through web.sock as fa's browser makes it, with its cookie jar; answers the status and the body."""
    words = [
        "runuser",
        "-u",
        "fa",
        "--",
        "curl",
        "-sS",
        "-o",
        "-",
        "-w",
        "\n%{http_code}",
        "-X",
        method,
        "--unix-socket",
        "/run/porelo-forge/web.sock",
        "-b",
        str(JAR / "jar"),
        "-c",
        str(JAR / "jar"),
        "-H",
        f"Host: {host}",
    ]
    for header in headers:
        words += ["-H", header]
    for key, value in (form or {}).items():
        words += ["--data-urlencode", f"{key}={value}"]
    parts = run(*words, f"http://{OWN}{route}").stdout.rpartition("\n")
    return parts[2], parts[0]


if FORGE_ON:
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

    def forge_admin(*words):
        # Forgejo's own admin command in its container, whose answers stay on this process's pipes.
        return run(
            "runuser", "-u", account, "--", "env", "-C", "/", f"XDG_RUNTIME_DIR=/run/user/{uid}",
            "podman", "exec", "forgejo", "forgejo", "admin", *words,
        )  # fmt: skip

    def forge_token_of(username, scopes):
        made = forge_admin(
            "user", "generate-access-token", "--username", username,
            "--token-name", f"follow-act-{scopes.replace(':', '-')}", "--scopes", scopes, "--raw",
        )  # fmt: skip
        value = made.stdout.strip()
        check(made.returncode == 0 and value, f"a {scopes} token of {username} for the act", made.stderr)
        return value

    forge_token = forge_token_of("porelo-admin", "all")

    def forge(method, route, body=None, token=None):
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
            given=f'header = "Authorization: token {token or forge_token}"\n',
        )
        text, unused, code = done.stdout.rpartition("\n")
        return int(code or 0), json.loads(text) if text.strip().startswith(("{", "[")) else None

    def package(method, secret, user="porelo-publisher", organization=PROJECT):
        # By default the one user name the shared settings send for every organization's publisher, not the token's
        # owner.
        done = run(
            "curl",
            "-sS",
            "-K",
            "-",
            "--unix-socket",
            socket,
            "-o",
            "/dev/null",
            "-X",
            method,
            "-w",
            "%{http_code}",
            # With curl's form content type the registry looks for a form's file and answers 500.
            *(["--data-binary", "probe", "-H", "content-type: application/octet-stream"] if method == "PUT" else []),
            f"http://localhost/api/packages/{organization}/generic/follow-act/1/probe",
            given=f'user = "{user}:{secret}"\n',
        )
        return done.stdout.strip()

    publisher = f"porelo-publisher-{PROJECT}"
    held = {item["name"] for item in forge("GET", f"orgs/{PROJECT}/actions/secrets")[1] or []}
    check("PORELO_PACKAGES_READ_TOKEN" in held, "the organization to hold the read token", held)
    check("PORELO_PUBLISHER_TOKEN" in held, "the organization to hold the publisher's token", held)
    if os.path.exists("/var/lib/porelo-host/pool/run-key"):
        # The real forge behind its gate: the project got the key from its add, and it can be taken and given again.
        def secrets():
            return {item["name"] for item in forge("GET", f"orgs/{PROJECT}/actions/secrets")[1] or []}

        def pool_key(direction):
            done = run(HELPER, "project", "pool-key", direction)
            check(done.returncode == 0, f"pool-key {direction} to answer 0", done.stdout + done.stderr)
            return json.loads(done.stdout or '{"changed":[]}')["changed"]

        check("PORELO_POOL_SSH" in held, "the organization to hold the pool's run key", held)
        answered = pool_key("send")
        check(PROJECT not in answered, "a key it holds not sent again", answered)
        answered = pool_key("withdraw")
        check(PROJECT in answered, "the key taken from the project", answered)
        check("PORELO_POOL_SSH" not in secrets(), "the key gone from the organization", secrets())
        check("PORELO_PACKAGES_READ_TOKEN" in secrets(), "only that secret taken", secrets())
        answered = pool_key("send")
        check(PROJECT in answered, "the key given to a project lacking it", answered)
        check("PORELO_POOL_SSH" in secrets(), "the key back in the organization", secrets())
    code, variable = forge("GET", f"orgs/{PROJECT}/actions/variables/MAVEN_SNAPSHOTS_URL")
    check(code == 200 and f"/api/packages/{PROJECT}/maven" in str(variable), "its own snapshot URL", variable)
    code, variable = forge("GET", f"orgs/{PROJECT}/actions/variables/MAVEN_UPSTREAM_SNAPSHOTS_URL")
    upstream = "https://central.sonatype.com/repository/maven-snapshots/"
    check(
        code == 200 and isinstance(variable, dict) and variable.get("data") == upstream,
        "the upstream snapshots",
        variable,
    )
    # The same scopes the helper asks for; the secrets themselves cannot be read back.
    reader, writer = forge_token_of(publisher, "read:package"), forge_token_of(publisher, "write:package")
    refused = package("PUT", reader)
    check(not refused.startswith("2"), "the read token not to write a package", refused)
    written = package("PUT", writer)
    check(written.startswith("2"), "the publisher's token to write a package", written)
    read = package("GET", reader)
    check(read == "200", "the read token to read the package", read)

    # A task's token, made by a real task start of fb's: it reads its project's snapshots, writes none, and reads no
    # organization fb is not in. Everything it makes goes again, also when a step fails.
    other = "follow-other"
    record = Path("/var/lib/porelo-host/tasks/fb/pkgread.json")
    try:
        code = forge("POST", "orgs", {"username": other, "visibility": "private"})[0]
        check(code == 201, "a second organization fb is not in", code)
        placed = package("PUT", forge_token, "porelo-admin", other)
        check(placed.startswith("2"), "a package in the second organization", placed)
        there = package("GET", forge_token, "porelo-admin", other)
        check(there == "200", "the second organization's package to be readable", there)
        with tempfile.TemporaryDirectory(prefix="task-act-") as task_keys:
            made = run("ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "", "-f", f"{task_keys}/task")
            check(made.returncode == 0, "a task key", made.stderr)
            signed = run(
                "ssh-keygen", "-q", "-s", str(KEYS / "fb"), "-I", "porelo task pkgread by fb",
                "-n", f"task:{PROJECT}:pkgread", "-V", "-5m:+1h", f"{task_keys}/task.pub",
            )  # fmt: skip
            check(signed.returncode == 0, "fb's certificate for the task", signed.stderr)
            issued = Path(f"{task_keys}/task-cert.pub")
            certificate = issued.read_text(encoding="utf-8") if issued.exists() else ""
        started = run("runuser", "-u", "fb", "--", "sudo", "-n", HELPER, "task", "start", "pkgread", given=certificate)
        # Its stdout is the token alone, so only stderr is ever shown.
        task_token = started.stdout.strip()
        check(started.returncode == 0 and task_token, "fb's task start to answer a token", started.stderr)
        if task_token:
            read = package("GET", task_token, "porelo-fb")
            check(read == "200", "the task's token to read its project's package", read)
            gone = package("DELETE", writer)
            check(gone.startswith("2"), "the act's package to go", gone)
            # On a name nobody holds, so only a refusal of the write itself answers other than 201.
            refused = package("PUT", task_token, "porelo-fb")
            check(refused in ("401", "403"), "the task's token refused a package write", refused)
            refused = package("GET", task_token, "porelo-fb", other)
            check(refused in ("401", "403", "404"), "the task's token refused another organization's package", refused)
    finally:
        ended = run("runuser", "-u", "fb", "--", "sudo", "-n", HELPER, "task", "end", "pkgread")
        check(ended.returncode == 0 or not record.exists(), "fb's task to end", ended.stderr)
        record.unlink(missing_ok=True)
        if record.parent.exists() and not any(record.parent.iterdir()):
            record.parent.rmdir()
        for organization in (PROJECT, other):
            package("DELETE", forge_token, "porelo-admin", organization)
        code = forge("DELETE", f"orgs/{other}")[0]
        check(code in (204, 404), "the second organization to go", code)
        for organization in (PROJECT, other):
            left = package("GET", forge_token, "porelo-admin", organization)
            check(left == "404", f"no package left in {organization}", left)

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

    def git(*words, token=None):
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
                "GIT_CONFIG_VALUE_0": f"Authorization: token {token or forge_token}",
            },
        )

    cloned = git("clone", "-q", f"http://127.0.0.1:{git_port}/{PROJECT}/{code_name}.git", ".")
    check(cloned.returncode == 0, "the act's repository to clone", cloned.stderr)

    def commit_on_main(name):
        for words in (("fetch", "-q", "origin", "main"), ("checkout", "-q", "-B", name, "origin/main")):
            git(*words)
        Path(checkout.name, f"{name.replace('/', '-')}.txt").write_text(name, encoding="utf-8")
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
    # As a Project Admin's rename leaves it: only the case differs, and Forgejo holds the older rule in force.
    forge("DELETE", f"{repository}/branch_protections/main")
    code, rule = forge("POST", f"{repository}/branch_protections", {"rule_name": "MAIN", "required_approvals": 0})
    check(code == 201, "a rule named MAIN to be made", [code, rule])
    followed()
    code, rules = forge("GET", f"{repository}/branch_protections")
    on_main = [item for item in rules or [] if item["rule_name"].lower() == "main"]
    check(len(on_main) == 1, "no second rule on main", rules)
    check(on_main and on_main[0]["required_approvals"] == 1, "a rule renamed in case to be set back", on_main)
    check(400 <= merged_alone("renamed") < 500, "the author not to merge alone under a renamed rule")
    # A task's pull request: opened by its own account with its task's token, approved and merged by its person, so a
    # project of one member merges under a required review. Its task goes again, also when a step fails.
    record = Path("/var/lib/porelo-host/tasks/fb/prown.json")
    try:
        with tempfile.TemporaryDirectory(prefix="task-act-") as task_keys:
            made = run("ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "", "-f", f"{task_keys}/task")
            check(made.returncode == 0, "a task key for the pull request", made.stderr)
            signed = run(
                "ssh-keygen", "-q", "-s", str(KEYS / "fb"), "-I", "porelo task prown by fb",
                "-n", f"task:{PROJECT}:prown", "-V", "-5m:+1h", f"{task_keys}/task.pub",
            )  # fmt: skip
            check(signed.returncode == 0, "fb's certificate for the pull request's task", signed.stderr)
            issued = Path(f"{task_keys}/task-cert.pub")
            certificate = issued.read_text(encoding="utf-8") if issued.exists() else ""
        started = run("runuser", "-u", "fb", "--", "sudo", "-n", HELPER, "task", "start", "prown", given=certificate)
        task_token = started.stdout.strip()
        check(started.returncode == 0 and task_token, "fb's task start to answer a token", started.stderr)
        if task_token:
            commit_on_main("porelo/prown")
            pushed = git("push", "-q", "origin", "porelo/prown", token=task_token)
            check(pushed.returncode == 0, "the task's token to push its branch", pushed.stderr)
            # An amend replaces the task's own branch; any other ref the host refuses the task's account, which it can
            # tell only from the pusher Forgejo names to the judge.
            amended = git("commit", "-q", "--amend", "--no-edit")
            check(amended.returncode == 0, "the task's commit amended and signed again", amended.stderr)
            forced = git("push", "-q", "--force-with-lease", "origin", "porelo/prown", token=task_token)
            check(forced.returncode == 0, "the task's token to force-push its own branch", forced.stderr)
            foreign = git("push", "-q", "origin", "HEAD:refs/heads/porelo/no-task-of-fb", token=task_token)
            check(
                foreign.returncode != 0 and "pushes only porelo/<task> of fb's own tasks" in foreign.stderr,
                "the host to refuse the task's token a branch of no task of its person",
                [foreign.returncode, foreign.stderr],
            )
            code, pull = forge(
                "POST", f"{repository}/pulls", {"head": "porelo/prown", "base": "main", "title": "prown"}, task_token
            )
            check(code == 201, "the task's token to open its pull request", [code, pull])
            author = (pull or {}).get("user", {}).get("login")
            check(author == "porelo-fb", "the pull request to be the task account's", author)
            number = (pull or {}).get("number")
            check(isinstance(number, int), "the pull request to have a number", pull)
            person_token = forge_token_of("fb", "write:repository")
            code = forge("POST", f"{repository}/pulls/{number}/merge", {"Do": "fast-forward-only"}, person_token)[0]
            check(number and 400 <= code < 500 and code != 404, "the pull request not to merge unapproved", code)
            # A writer outside Owners and developers approves: Forgejo takes the review, and it counts for nothing.
            # Its password is Forgejo's own random one, on no command line and read by nobody.
            made = forge_admin(
                "user", "create", "--username", "follow-outsider", "--email", "outsider@example.org",
                "--random-password", "--must-change-password=false",
            )  # fmt: skip
            check(made.returncode == 0, "an account outside the project's teams", made.stderr)
            code = forge("PUT", f"{repository}/collaborators/follow-outsider", {"permission": "write"})[0]
            check(code == 204, "the outsider to write the repository", code)
            outsider_token = forge_token_of("follow-outsider", "write:repository")
            code = forge("POST", f"{repository}/pulls/{number}/reviews", {"event": "APPROVED"}, outsider_token)[0]
            check(code == 200, "the outsider's approval to be taken as a review", code)
            code = forge("POST", f"{repository}/pulls/{number}/merge", {"Do": "fast-forward-only"}, person_token)[0]
            check(400 <= code < 500 and code != 404, "an outsider's approval not to let it merge", code)
            code, review = forge("POST", f"{repository}/pulls/{number}/reviews", {"event": "APPROVED"}, person_token)
            check(code == 200, "fb to approve its task's pull request", [code, review])
            code = forge("POST", f"{repository}/pulls/{number}/merge", {"Do": "fast-forward-only"}, person_token)[0]
            check(code == 200, "fb to merge its task's pull request under a required review", code)
    finally:
        forge("DELETE", "admin/users/follow-outsider?purge=true")
        ended = run("runuser", "-u", "fb", "--", "sudo", "-n", HELPER, "task", "end", "prown")
        check(ended.returncode == 0 or not record.exists(), "fb's pull request task to end", ended.stderr)
        record.unlink(missing_ok=True)
        if record.parent.exists() and not any(record.parent.iterdir()):
            record.parent.rmdir()
    # Every person's running user manager holds porelo-people, which opens the host's Matrix gate to their porelod.
    people = run("getent", "group", "porelo-people").stdout.split(":")
    for login in ("fa", "fb"):
        user_id = run("id", "-u", login).stdout.strip()
        pid = run("systemctl", "show", "--property=MainPID", "--value", f"user@{user_id}.service").stdout.strip()
        running = pid.isdecimal() and int(pid) > 0
        check(running, f"{login}'s user manager to run", pid)
        held = next(
            (line.split()[1:] for line in Path(f"/proc/{pid}/status").read_text().splitlines()
             if line.startswith("Groups:")),
            [],
        ) if running else []  # fmt: skip
        check(len(people) > 2 and people[2] in held, f"{login}'s user manager to hold porelo-people", held)
    # What org status says of each row: taken, waiting for the token this follow has not, and with no central.
    done_row = f"git@example.org:{PROJECT}/done.git"
    entries = json.loads(PROGRESS.read_text(encoding="utf-8"))
    entries[PROJECT]["taken"] = [done_row]
    entries[PROJECT]["file"]["repositories"] = {
        "done": {"review": "required", "central": done_row},
        "later": {"review": "required", "central": f"git@example.org:{PROJECT}/later.git"},
        "local": {"review": "optional", "central": None},
    }
    PROGRESS.write_text(json.dumps(entries), encoding="utf-8")
    followed()
    said = {row["repository"]: row["state"] for row in project_state()["repositories"]}
    check(said == {"done": "taken", "later": "waiting", "local": "no-central"}, "each row named", project_state())
    check("local" not in str(project_state()["why"]), "no row with no central in the project's why", project_state())

    # Taking one repository off, as the follow asks it of the root helper: the scenario has no central forge, so this
    # holds the verb to its form on the host, and the unit tests hold what it does at a central forge.
    taker = HELPER
    done = run(taker, "project", "take-off", PROJECT, given=json.dumps({"repository": "absent", "token": 7}))
    check(done.returncode == 64, "take-off to refuse a token that is no text", done.returncode)
    done = run(taker, "project", "take-off", PROJECT, given=json.dumps({"repository": "absent", "token": None}))
    check(
        done.returncode == 0 and json.loads(done.stdout or "{}").get("removed") is True,
        "take-off of a repository the host does not hold to answer it taken off",
        (done.returncode, done.stderr),
    )
    code = forge("GET", f"repos/{PROJECT}/{code_name}")[0]
    check(code == 200, "the project's own repository untouched by taking off one it does not hold", code)
    FETCH = ("Sec-Fetch-Site: none", "Sec-Fetch-Mode: navigate")
    SAME = (f"Origin: http://{OWN}", "Sec-Fetch-Site: same-origin", "Sec-Fetch-Mode: navigate")
    code, page = browser("GET", "/repo/create", FETCH)
    owner = re.search(r'name="uid" value="([0-9]+)"', page)
    check(code == "200" and owner, "fa's browser to open the form to create a repository", [code, page[:300]])
    form = {"uid": owner.group(1) if owner else "", "repo_name": "gate-own-site"}
    # A form token where this Forgejo still renders one; without one it judges the request's origin itself.
    token = re.search(r'name="_csrf" value="([^"]+)"', page)
    if token:
        form["_csrf"] = token.group(1)
    code = browser("POST", "/repo/create", SAME, form)[0]
    check(code == "303", "fa's browser to create a repository by its form", code)
    code = forge("GET", "repos/fa/gate-own-site")[0]
    check(code == 200, "the repository fa's browser created to exist", code)
    for name, headers in (
        ("gate-cross-origin", ("Origin: http://evil.example", "Sec-Fetch-Site: cross-site")),
        ("gate-cross-site", (f"Origin: http://{OWN}", "Sec-Fetch-Site: cross-site")),
        ("gate-other-origin", ("Origin: http://evil.example",)),
    ):
        code = browser("POST", "/repo/create", headers, dict(form, repo_name=name))[0]
        check(code == "403", f"a form from another site not to create {name}", code)
        code = forge("GET", f"repos/fa/{name}")[0]
        check(code == 404, f"no repository {name}", code)
    code = browser("GET", "/", FETCH, host=f"evil.example:{SITE['port']}")[0]
    check(code == "403", "a page asked for by another name to be refused", code)
    # Without the cookie, so only the gate's sign-in can open a form that needs one.
    (JAR / "jar").unlink(missing_ok=True)
    code, page = browser("GET", "/repo/create", FETCH, host=f"127.0.0.1:{SITE['port']}")
    check(code == "200" and 'name="uid"' in page, "fa signed in by 127.0.0.1", [code, page[:300]])
    code = forge("DELETE", "repos/fa/gate-own-site")[0]
    check(code == 204, "the browser's repository removed", code)
    # A job on the forge's runner is told where the host's pool is, as no job on GitHub is: one workflow then takes a
    # pool account here and rents a server there. Where the host has no pool, the job is told nothing.
    pooled = os.path.exists("/etc/porelo-host/pool/pool.json")
    told = (
        'test "${PORELO_MACHINES_POOL:-}" = /etc/porelo-host/pool/pool.json\n'
        '          grep -q porelo-machines-pool/1 "$PORELO_MACHINES_POOL"'
        if pooled
        else 'test -z "${PORELO_MACHINES_POOL:-}"'
    )
    git("fetch", "-q", "origin", "main")
    git("checkout", "-q", "-B", "pool-job", "origin/main")
    workflow = Path(checkout.name, ".forgejo/workflows/pool.yml")
    workflow.parent.mkdir(parents=True)
    workflow.write_text(
        "on: push\njobs:\n  pool:\n    runs-on: porelo-host\n    steps:\n      - shell: sh\n        run: |\n"
        f"          set -eu\n          {told}\n",
        encoding="utf-8",
    )
    git("add", ".")
    made = git("commit", "-q", "-m", "pool-job")
    check(made.returncode == 0, "a signed commit with the pool job", made.stderr)
    pushed = git("push", "-q", "origin", "pool-job")
    check(pushed.returncode == 0, "the judge to take the pool job's branch", pushed.stderr)
    job_state = None
    for _ in range(120):
        code, tasks = forge("GET", f"{repository}/actions/tasks")
        runs = (tasks or {}).get("workflow_runs") or [] if code == 200 else []
        job_state = next((r.get("status") for r in runs if r.get("head_branch") == "pool-job"), None)
        if job_state in ("success", "failure", "cancelled", "skipped"):
            break
        subprocess.run(["sleep", "5"], check=False)
    check(
        job_state == "success",
        "a job on the forge to be told the pool" if pooled else "a job on a forge without a pool to be told none",
        job_state,
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
done = helper("org", "follow", expected=65)
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
done = helper("org", "follow", expected=69)
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
PERSONS = ORG / "persons"
check(can_read("fa", PERSONS / "fa.json") and can_read("fc", PERSONS / "fc.json"), "each to read their own list")
check(not can_read("fa", PERSONS / "fc.json"), "fa not to read fc's list")
check(not can_read("fc", PERSONS / "fa.json"), "fc not to read fa's list")
check(run("runuser", "-u", "fa", "--", "ls", "--", str(PERSONS)).returncode != 0, "fa not to list who has a list")
check(not (PERSONS / "fb.json").exists(), "revoked fb to have no list")
if FORGE_ON:
    check(public("fb") not in ALLOWED.read_text(encoding="utf-8"), "fb's key out of the allowed signers")

# A membership lost: locked with a day to go, and back when the state says so.
answer("d", admins=["hostadmin"], persons=EVERYONE, revoked=["fb"], projects={})
helper("org", "follow")
check(not RECORD.exists(), "the project taken off the host's forge", project_state())
check(not ACCESS.exists() and not ALLOWED.exists() and not CERTIFIERS.exists(), "nothing of the project to stay")
check(not (PERSONS / "fa.json").exists(), "fa's list gone with the last membership")
check(project_state() is None, "org status not to name the project", project_state())
seen = person("fa")
day = (datetime.date.today() + datetime.timedelta(days=7)).isoformat()
check(seen["state"] == "locked" and seen.get("purge_on") == day, f"fa locked until {day}", seen)
check(not reaches("fa"), "fa stopped at SSH with no membership left")
answer("e", admins=["hostadmin"], persons=EVERYONE, revoked=["fb"], projects={PROJECT: {"fa": "admin"}})
helper("org", "follow")
seen = person("fa")
check(seen["state"] == "active" and "purge_on" not in seen and reaches("fa"), "fa back with its membership", seen)

# A purge removes both the person's and task's homeserver accounts; the 200 shows the question
# can tell. Only while the person is a member does the gate let them make one.
ACCOUNTS = [matrix_account("fa", "fa"), matrix_account("fa", "task.fa")]
check([matrix_answers(access) for access in ACCOUNTS] == ["200", "200"], "fa's accounts to act before the purge")

# What the act leaves is nothing of its persons, for the next one.
answer("f", admins=["hostadmin"], persons=["hostadmin"], projects={})
helper("org", "follow")
for login in ("fa", "fb", "fc"):
    check(person(login)["state"] == "locked", f"{login} to be locked after removal", person(login))
print("SKIPPED: manual purge has no packaged verb; org follow purges only after seven days")

journal = run("journalctl", "-b", "--no-pager").stdout
check(TOKEN not in journal, "the token to stay out of the journal")
check(run("systemctl", "start", "porelo-host-follow.timer").returncode == 0, "the timer started again")
sys.exit("; ".join(WRONG) if WRONG else 0)
