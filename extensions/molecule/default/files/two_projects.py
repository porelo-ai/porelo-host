"""Two projects brought by their own admins, one developer with two laptops in both, joined, taken off.

Runs as root on the Molecule VM with -I. It prints one JSON line of facts, never a secret; on a failure it prints
only the stage, the line, the exception's class, an HTTP code or exit status and, for a host tool, its own refusal
line, which names no secret; for a playbook only the name of its last task.
"""

import base64
import json
import os
import pathlib
import pwd
import re
import secrets
import shutil
import ssl
import subprocess
import sys
import traceback
import urllib.error
import urllib.request

WORK = pathlib.Path("/root/verify-two")
OUT = WORK / "act.out"
PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
PROJECTS = {"gamma-one": "ga", "gamma-two": "gb"}
DEVELOPER = "gd"
LAPTOP_ADDRESSES = ("10.73.7.40", "10.73.7.41")
PATTERNS = []
STAGE = {"name": "start"}


class Refused(Exception):
    """A command that answered with a status other than 0."""

    def __init__(self, what, returncode, tail):
        super().__init__(what)
        self.what = what
        self.returncode = returncode
        self.tail = tail


def redact(text):
    for item in PATTERNS:
        text = text.replace(item, "<redacted>")
    return text


def failed(kind, error, tb):
    lines = [f.lineno for f in traceback.extract_tb(tb) if f.filename == __file__]
    print(
        json.dumps(
            {
                "failed_at": STAGE["name"],
                "failed_at_line": lines[-1] if lines else None,
                "lines": lines,
                "error": kind.__name__,
                "what": getattr(error, "what", None),
                "code": getattr(error, "code", None),
                "returncode": getattr(error, "returncode", None),
                "tail": getattr(error, "tail", None),
            }
        ),
        flush=True,
    )
    os._exit(0)


sys.excepthook = failed


def secret(value):
    if value and value not in PATTERNS:
        PATTERNS.append(value)
    return value


def record_output(run):
    with OUT.open("a", encoding="utf-8") as handle:
        handle.write(run.stdout + run.stderr)


def said(name, done):
    """What a failed command may show: a host tool's refusal line, or a playbook's last task name, never output."""
    if name.startswith("/usr/local/sbin/porelo-host-"):
        lines = redact(done.stderr).strip().splitlines()
        return lines[-1][:300] if lines else None
    tasks = [line for line in done.stdout.splitlines() if line.startswith("TASK [")]
    return tasks[-1][:300] if tasks else None


def run(argv, stdin="", user=None, check=True, keep=True):
    """Run as root or as a person in their own account, keeping the output for the leak scan."""
    cwd = "/"
    if user is not None:
        pw = pwd.getpwnam(user)
        cwd = pw.pw_dir
        argv = [
            "/usr/sbin/runuser",
            "-u",
            user,
            "--",
            "/usr/bin/env",
            f"HOME={pw.pw_dir}",
            f"USER={user}",
            f"LOGNAME={user}",
            f"XDG_RUNTIME_DIR=/run/user/{pw.pw_uid}",
            f"PATH={PATH}",
            "ANSIBLE_NOCOLOR=1",
            "LC_ALL=C.UTF-8",
            *argv,
        ]
    done = subprocess.run(argv, input=stdin, capture_output=True, text=True, cwd=cwd)
    if keep:
        record_output(done)
    if check and done.returncode != 0:
        name = next((part for part in argv if part.startswith(("/usr/local/", "porelo"))), argv[0])
        raise Refused(name, done.returncode, said(name, done))
    return done


def write_private(path, content, user=None):
    path = pathlib.Path(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        os.fchmod(handle.fileno(), 0o600)
        handle.write(content)
    if user is not None:
        pw = pwd.getpwnam(user)
        os.chown(path, pw.pw_uid, pw.pw_gid)


forge_token = secret(
    pathlib.Path("/home/porelo-forge/.config/porelo-forge/api.token").read_text(encoding="utf-8").strip()
)
forge_uid = pwd.getpwnam("porelo-forge").pw_uid
context = ssl.create_default_context(cafile="/etc/porelo-host/forge/ca.pem")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=context))
BASE = "https://10.73.7.1:3000"


def api(method, path, body=None):
    request = urllib.request.Request(
        BASE + "/api/v1" + path,
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        method=method,
        headers={"Authorization": "token " + forge_token, "Content-Type": "application/json"},
    )
    try:
        with opener.open(request, timeout=30) as response:
            raw = response.read()
            return response.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as error:
        error.close()
        return error.code, None


def forge_cli(*args, keep=False):
    done = run(
        [
            "/usr/sbin/runuser",
            "-u",
            "porelo-forge",
            "--",
            "/usr/bin/env",
            f"XDG_RUNTIME_DIR=/run/user/{forge_uid}",
            "/usr/bin/podman",
            "exec",
            "forgejo",
            "forgejo",
            "admin",
            "user",
            *args,
        ],
        keep=keep,
    )
    return done.stdout.strip()


def person_record(user):
    path = pathlib.Path(f"/etc/porelo-host/people/{user}.conf")
    return path.read_text(encoding="utf-8") if path.exists() else None


def authorized_keys(user):
    path = pathlib.Path(f"/etc/ssh/authorized_keys/{user}")
    return (
        sorted(" ".join(line.split()[-2:]) for line in path.read_text().splitlines() if line) if path.exists() else []
    )


def wg_peers():
    return set(run(["/usr/bin/wg", "show", "wg-porelo", "peers"], keep=False).stdout.split())


def install_collection(user):
    # A person logs in before acting; here the user manager, which makes their runtime directory, is started.
    pw = pwd.getpwnam(user)
    run(["/usr/bin/systemctl", "start", f"user@{pw.pw_uid}.service"], keep=False)
    staged = pathlib.Path(pw.pw_dir) / ".porelo-host-install.tar.gz"
    shutil.copyfile("/root/porelo-host.tar.gz", staged)
    os.chown(staged, pw.pw_uid, pw.pw_gid)
    os.chmod(staged, 0o600)
    try:
        run(["ansible-galaxy", "collection", "install", "--force", str(staged)], user=user)
    finally:
        staged.unlink(missing_ok=True)


def keep_waiting_tokens(user):
    path = pathlib.Path(f"/run/porelo-host/people/{user}/identities.tokens")
    for line in path.read_text(encoding="utf-8").splitlines() if path.exists() else []:
        secret(line.split(" ")[-1])


def own_stop(user, central=None):
    keep_waiting_tokens(user)
    passphrase = secret(f"{user}-vault-passphrase-" + secrets.token_hex(20))
    lines = ["vault-new " + base64.b64encode(passphrase.encode()).decode()]
    names = ["vault-new"]
    if central is not None:
        lines.append("forge-central-token " + base64.b64encode(central.encode()).decode())
        names.append("forge-central-token")
    run(["/usr/local/bin/porelo-host-stop", "--stdin", *names, "identities"], stdin="\n".join(lines) + "\n", user=user)


def setup_directory(user, project):
    pw = pwd.getpwnam(user)
    directory = pathlib.Path(pw.pw_dir)
    for part in (".local", "share", "porelo-host", "setup", project):
        directory = directory / part
        directory.mkdir(mode=0o700, exist_ok=True)
        os.chown(directory, pw.pw_uid, pw.pw_gid)
        directory.chmod(0o700)
    return directory


def upload(user, project, machine_yml, access_only=False):
    directory = setup_directory(user, project)
    names = ["access.bundle"] if access_only else ["project.bundle", "access.bundle"]
    for name in names:
        target = directory / name
        shutil.copyfile(WORK / project / name, target)
        os.chown(target, pwd.getpwnam(user).pw_uid, pwd.getpwnam(user).pw_gid)
        target.chmod(0o600)
    if machine_yml is not None:
        write_private(directory / "machine.yml", machine_yml, user)
    return directory


GIT_ENV = {
    "PATH": PATH,
    "LC_ALL": "C.UTF-8",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_NOSYSTEM": "1",
    "HOME": str(WORK / "git-home"),
}


def git(*args):
    return subprocess.run(["/usr/bin/git", *args], env=GIT_ENV, check=True, capture_output=True, text=True).stdout


def signed_bundle(project, kind, filename, content):
    """Commit one file signed with the project's key onto its repository's main and bundle every commit."""
    repo = WORK / project / f"{kind}-repo"
    if not repo.exists():
        git("init", "-q", "-b", "main", str(repo))
    (repo / filename).write_text(content, encoding="utf-8")
    git("-C", str(repo), "add", filename)
    git(
        "-C",
        str(repo),
        "-c",
        "user.name=Gamma Signer",
        "-c",
        "user.email=signer@example.org",
        "-c",
        "gpg.format=ssh",
        "-c",
        f"user.signingkey={WORK / project / 'signer'}",
        "commit",
        "-q",
        "-S",
        "-m",
        f"Sign {filename}",
    )
    bundle = WORK / project / f"{kind}.bundle"
    bundle.unlink(missing_ok=True)
    git("-C", str(repo), "bundle", "create", "-q", str(bundle), "--all")
    bundle.chmod(0o600)
    return git("-C", str(repo), "rev-parse", "HEAD").strip()


def access_yml(project, developers):
    host = json.loads(pathlib.Path("/etc/porelo-host/host.json").read_text(encoding="utf-8"))
    return (
        json.dumps(
            {
                "host": {
                    key: host[key]
                    for key in ("address", "endpoint", "wireguard_public_key", "network", "ssh_host_key", "ca_sha256")
                },
                "developers": developers,
                "transports": {
                    "matrix": {
                        "homeserver": "https://matrix.alpha.porelo.internal:8448",
                        "room": f"#porelo-{project}:matrix.alpha.porelo.internal",
                        "registration_token_file": "~/.config/porelo/matrix/host-registration-token",
                        "ca_certificate": pathlib.Path("/etc/porelo-host/forge/ca.pem").read_text(encoding="ascii"),
                    }
                },
            },
            indent=2,
        )
        + "\n"
    )


def project_yml(project, signer):
    return (
        f"project:\n  name: {project}\n  security_class: guarded\n  signers:\n    - {json.dumps(signer)}\n"
        "image:\n  base_image: ubuntu:24.04\n"
        f"access:\n  repository: https://forge.invalid/{project}/access.git\n"
        'mail:\n  peers:\n    people:\n      address: "matrix:"\n      trust: external\n'
    )


def laptop_keys(tag):
    key = WORK / f"{tag}.ssh"
    subprocess.run(["/usr/bin/ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "", "-f", str(key)], check=True)
    ssh = " ".join(key.with_suffix(".ssh.pub").read_text(encoding="utf-8").split()[:2])
    private = subprocess.run(["/usr/bin/wg", "genkey"], check=True, capture_output=True, text=True).stdout
    wg = subprocess.run(["/usr/bin/wg", "pubkey"], input=private, check=True, capture_output=True, text=True)
    return ssh, wg.stdout.strip()


def following(user):
    done = run(["porelo", "project", "following", "--json"], user=user)
    return {
        entry["name"]: {"verified": entry.get("verified"), "commit": entry.get("commit")}
        for entry in json.loads(done.stdout).get("follows", [])
    }


def push_lines(user, project):
    path = pathlib.Path(pwd.getpwnam(user).pw_dir) / ".config/porelo-host/push" / f"{project}.conf"
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else None


facts = {}
shutil.rmtree(WORK, ignore_errors=True)
WORK.mkdir(mode=0o700)
(WORK / "git-home").mkdir(mode=0o700)
OUT.touch(mode=0o600)

STAGE["name"] = "keys"
laptops = [laptop_keys(f"{DEVELOPER}-{index}") for index in (1, 2)]
admin_lines = {}
for project, admin in PROJECTS.items():
    (WORK / project).mkdir(mode=0o700)
    signer = WORK / project / "signer"
    subprocess.run(["/usr/bin/ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "", "-f", str(signer)], check=True)
    ssh, wg = laptop_keys(admin)
    admin_lines[admin] = f"{admin}-laptop {ssh} {wg}\n"

STAGE["name"] = "admit and register"
for project, admin in PROJECTS.items():
    run(["/usr/local/sbin/porelo-host-person", "add", admin, "--role", "project-admin"], stdin=admin_lines[admin])
    signer = " ".join((WORK / project / "signer.pub").read_text(encoding="utf-8").split()[:2])
    (WORK / project / "signer.line").write_text(signer + "\n", encoding="utf-8")
    run(["/usr/local/sbin/porelo-host-project", "add", project, admin, "--signed-by", signer])

STAGE["name"] = "central forge"
# A reader of the central repositories of its own, deleted with its tokens at cleanup.
forge_cli(
    "create",
    "--username",
    "central-gr",
    "--email",
    "central-gr@example.invalid",
    "--random-password",
    "--must-change-password=false",
)
central_token = secret(
    forge_cli(
        "generate-access-token",
        "--username",
        "central-gr",
        "--token-name",
        "verify-two-" + secrets.token_hex(8),
        "--scopes",
        "read:repository",
        "--raw",
    )
)
if not re.fullmatch(r"[0-9a-f]{40}", central_token):
    raise RuntimeError("no central token")
central = {}
for project in PROJECTS:
    org = f"central-{project}"
    statuses = [
        api("POST", "/orgs", {"username": org, "visibility": "public"})[0],
        api("POST", f"/orgs/{org}/repos", {"name": "app", "private": False, "auto_init": False})[0],
        api(
            "POST",
            f"/repos/{org}/app/contents/README.md",
            {"branch": "main", "content": base64.b64encode(f"# {org}\n".encode()).decode(), "message": "Add README"},
        )[0],
    ]
    if statuses != [201, 201, 201]:
        raise RuntimeError(f"central {org} answered {statuses}")
    central[project] = f"{BASE}/{org}/app.git"

STAGE["name"] = "bundles"
developer_spec = {
    DEVELOPER: {
        "laptops": [
            {"ssh_public_key": ssh, "wireguard_public_key": wg, "vpn_address": address}
            for (ssh, wg), address in zip(laptops, LAPTOP_ADDRESSES)
        ]
    }
}
commits = {}
for project in PROJECTS:
    signer = (WORK / project / "signer.line").read_text(encoding="utf-8").strip()
    commits[project] = {
        "project": signed_bundle(project, "project", "project.yml", project_yml(project, signer)),
        "access": signed_bundle(project, "access", "access.yml", access_yml(project, developer_spec)),
    }

records = {}
for project, admin in PROJECTS.items():
    STAGE["name"] = f"bring {project} as {admin}"
    install_collection(admin)
    signer = (WORK / project / "signer.line").read_text(encoding="utf-8").strip()
    upload(
        admin,
        project,
        f"project:\n  name: {project}\n"
        f"  url: {pwd.getpwnam(admin).pw_dir}/.local/share/porelo-host/setup/{project}/project.bundle\n"
        f"  signed_by: {json.dumps(signer)}\nkeys: []\naccess:\n  bundle: access.bundle\n"
        f"forge:\n  repositories:\n    - name: app\n      url: {json.dumps(central[project])}\n",
    )
    own_stop(admin, central_token)
    run(["ansible-playbook", "-c", "local", "porelo.host.bring", "-e", f"porelo_project={project}"], user=admin)
    records[f"after {project}"] = person_record(DEVELOPER)

facts["accounts"] = sorted(
    entry.pw_name for entry in pwd.getpwall() if entry.pw_name == DEVELOPER or entry.pw_name.startswith(DEVELOPER)
)
facts["records"] = records
facts["keys_wanted"] = sorted(ssh for ssh, _ in laptops)
facts["keys_after_bring"] = authorized_keys(DEVELOPER)
facts["peers_after_bring"] = sum(wg in wg_peers() for _, wg in laptops)

STAGE["name"] = "join both as the developer"
install_collection(DEVELOPER)
own_stop(DEVELOPER)
for project in PROJECTS:
    signer = (WORK / project / "signer.line").read_text(encoding="utf-8").strip()
    upload(
        DEVELOPER,
        project,
        f"project:\n  name: {project}\n"
        f"  url: {pwd.getpwnam(DEVELOPER).pw_dir}/.local/share/porelo-host/setup/{project}/project.bundle\n"
        f"  signed_by: {json.dumps(signer)}\nkeys: []\naccess:\n  bundle: access.bundle\n",
    )
    run(["ansible-playbook", "-c", "local", "porelo.host.join", "-e", f"porelo_project={project}"], user=DEVELOPER)
facts["push"] = {project: push_lines(DEVELOPER, project) for project in PROJECTS}
facts["central"] = central
facts["following"] = following(DEVELOPER)
facts["commits"] = commits

STAGE["name"] = "take gamma-two off"
facts["gamma_two_app_deleted"] = api("DELETE", "/repos/gamma-two/app")[0]
removed = run(["/usr/local/sbin/porelo-host-project", "remove", "gamma-two"])
facts["gamma_two_removed"] = json.loads(removed.stdout)
facts["record_after_remove"] = person_record(DEVELOPER)
facts["keys_after_remove"] = authorized_keys(DEVELOPER)

STAGE["name"] = "drop the developer from gamma-one"
commits["gamma-one"]["access_without"] = signed_bundle("gamma-one", "access", "access.yml", access_yml("gamma-one", {}))
upload(PROJECTS["gamma-one"], "gamma-one", None, access_only=True)
run(["systemctl", "--user", "start", "porelo-host-sync-gamma-one.service"], user=PROJECTS["gamma-one"])
facts["record_after_drop"] = person_record(DEVELOPER)
facts["keys_after_drop"] = authorized_keys(DEVELOPER)
facts["peers_after_drop"] = sum(wg in wg_peers() for _, wg in laptops)

STAGE["name"] = "leak scan"
captured = OUT.read_text(encoding="utf-8")
journal = subprocess.run(
    ["/usr/bin/journalctl", "--no-pager", "-q", "-o", "cat"], capture_output=True, text=True, check=True
)
facts["patterns"] = len(PATTERNS)
facts["leaks"] = sum(item in captured or item in journal.stdout for item in PATTERNS)
print(json.dumps(facts))
