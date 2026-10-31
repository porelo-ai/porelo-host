"""Guard the forge tokens the host makes for a person and each task, and the task certificates it records."""

import base64
import datetime
import hashlib
import io
import json
import os
import runpy
import shutil
import stat
import struct
import subprocess
import tempfile
import urllib.error
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "roles/porelo/files/porelo-host-person"
ADMIN = "porelo-admin"
NOW = datetime.datetime(2026, 10, 30, 12, 0, tzinfo=datetime.timezone.utc)
# Certificates are made with ssh-keygen's UTC form, so they hold against NOW whatever the machine's zone is.
TODAY = "20261030000000Z:20261031000000Z"
SSH_KEYGEN = shutil.which("ssh-keygen")

pytestmark = pytest.mark.skipif(SSH_KEYGEN is None, reason="ssh-keygen is not installed")


def fixture_key(number):
    blob = struct.pack(">I", 11) + b"ssh-ed25519" + struct.pack(">I", 32) + bytes([number]) * 32
    return "ssh-ed25519 " + base64.b64encode(blob).decode()


def fixture_fingerprint(key):
    blob = base64.b64decode(key.split(" ", 1)[1])
    return "SHA256:" + base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip("=")


class Keys:
    """Real Ed25519 keys and certificates from ssh-keygen, in a directory outside the host's root."""

    def __init__(self, directory):
        self.directory = directory
        directory.mkdir(mode=0o700)

    def make(self, name):
        path = self.directory / name
        made = subprocess.run(
            [SSH_KEYGEN, "-q", "-t", "ed25519", "-N", "", "-C", "", "-f", str(path)], capture_output=True, text=True
        )
        assert made.returncode == 0, made.stderr
        return " ".join(path.with_suffix(".pub").read_text().split()[:2])

    def certify(self, signer, task_key, principals, valid=TODAY, host=False, key_id="porelo task"):
        """Sign task_key's public half with signer's private key, as the person's Porelo does at a task's start."""
        public = self.directory / (task_key + ".pub")
        certificate = self.directory / (task_key + "-cert.pub")
        certificate.unlink(missing_ok=True)
        made = subprocess.run(
            [
                SSH_KEYGEN,
                "-q",
                "-s",
                str(self.directory / signer),
                "-I",
                key_id,
                "-n",
                ",".join(principals),
                "-V",
                valid,
                *(["-h"] if host else []),
                str(public),
            ],
            capture_output=True,
            text=True,
        )
        assert made.returncode == 0, made.stderr
        return certificate.read_text()

    def fingerprint(self, name):
        return fixture_fingerprint(" ".join((self.directory / (name + ".pub")).read_text().split()[:2]))


class Forge:
    """Forgejo's admin command and admin API as far as the host uses them, keeping each user's tokens by name."""

    def __init__(self, scope):
        self.scope = scope
        self.tokens = {}
        self.next = 1
        self.calls = []
        self.requests = []
        self.api_failure = None
        self.checks = []
        self.check_answer = None
        self.verifies = []
        self.verify_answer = None
        self.gitea = None
        self.timeouts = []

    def secret(self):
        value = hashlib.sha1(f"fixture-token-{self.next}".encode()).hexdigest()
        self.next += 1
        return value

    def named(self, user):
        return sorted(item["name"] for item in self.tokens.get(user, {}).values())

    def secrets(self):
        return [item["secret"] for tokens in self.tokens.values() for item in tokens.values()]

    def run(self, args, input=None, timeout=60):
        self.calls.append(args)
        self.timeouts.append(timeout)
        if args[:3] == ["env", "TZ=UTC", "ssh-keygen"]:
            return self.scope["run_command"](args)
        if args[:1] == ["systemd-run"] and "commit" in args:
            return self.commit_verify(args, input)
        if args[:1] == ["systemd-run"]:
            return self.check_certificate(args, input)
        assert args[:2] == ["runuser", "-u"] and args[2] == "porelo-forge", args
        offset = args.index("podman")
        if args[offset : offset + 5] == ["podman", "exec", "forgejo", "sh", "-c"]:
            return self.forge_shell(args, args[offset + 5], args[offset + 7 :])
        if args[offset:] == ["podman", "exec", "forgejo", "forgejo", "admin", "user", "list"]:
            return subprocess.CompletedProcess(
                args,
                0,
                "ID Username Email IsActive IsAdmin\n"
                "1 alice alice@example.org true false\n"
                "2 porelo-alice gate@example.org true false\n"
                "3 porelo-admin admin@example.org true true\n",
                "",
            )
        assert args[offset : offset + 7] == [
            "podman",
            "exec",
            "forgejo",
            "forgejo",
            "admin",
            "user",
            "generate-access-token",
        ], args
        user = args[args.index("--username") + 1]
        name = args[args.index("--token-name") + 1]
        tokens = self.tokens.setdefault(user, {})
        if any(item["name"] == name for item in tokens.values()):
            return subprocess.CompletedProcess(args, 1, "", "access token name has been used already")
        secret = self.secret()
        tokens[self.next] = {"name": name, "scopes": args[args.index("--scopes") + 1], "secret": secret}
        self.next += 1
        return subprocess.CompletedProcess(args, 0, secret + "\n", "")

    def commit_verify(self, args, input):
        """Porelo's commit verify as the contract answers: what it was given is kept, its answer is the test's."""
        staged = dict(item.split("=", 1)[1].split(":", 1) for item in args if item.startswith("LoadCredential="))
        unit = next(item for item in args if item.startswith("--unit=")).removeprefix("--unit=")
        inside = {f"/run/credentials/{unit}.service/{name}": path for name, path in staged.items()}
        given = {
            option: Path(inside[args[args.index(option) + 1]]).read_bytes()
            for option in ("--signers", "--certifiers", "--krl", "--certificates")
        }
        self.verifies.append({"args": args, "input": input, "given": given})
        if self.verify_answer is not None:
            return self.verify_answer(args)
        commits = [
            {
                "commit": line.split()[1],
                "ref": line.split()[2],
                "verdict": "accepted",
                "signer": {"kind": "person", "fingerprint": "SHA256:" + "B" * 43},
            }
            for line in input.splitlines()
        ]
        answer = {"checked_at": "2026-10-30T12:00:00Z", "accepted": True, "commits": commits}
        return subprocess.CompletedProcess(args, 0, json.dumps(answer) + "\n", "")

    def forge_shell(self, args, script, arguments):
        """The forge container's shell, run for real on a stand-in of its data, with a git that lists a file."""
        bin_dir = self.gitea / "bin"
        bin_dir.mkdir(exist_ok=True)
        git = bin_dir / "git"
        git.write_text('#!/bin/sh\nhistory="${1#--git-dir=}/history"\n[ -f "$history" ] || exit 128\ncat "$history"\n')
        git.chmod(0o755)
        hook = self.gitea / "pre-receive-hook"
        if not hook.exists() and not getattr(self, "no_hook", False):
            hook.write_text("#!/bin/sh\n")
            hook.chmod(0o755)
        script = script.replace("/var/lib/gitea/", str(self.gitea) + "/").replace(PUSH_HOOK, str(hook))
        environment = {"PATH": f"{bin_dir}:/usr/bin:/bin", "LC_ALL": "C"}
        return subprocess.run(["sh", "-c", script, "sh", *arguments], capture_output=True, text=True, env=environment)

    def check_certificate(self, args, input):
        """Porelo's task check-certificate as its contract answers, judging the signer with the real ssh-keygen."""
        offset = args.index("porelo")
        assert args[offset + 1 : offset + 3] == ["task", "check-certificate"], args
        staged = dict(item.split("=", 1)[1].split(":", 1) for item in args if item.startswith("LoadCredential="))
        unit = next(item for item in args if item.startswith("--unit=")).removeprefix("--unit=")
        # Inside the unit a credential is only at /run/credentials/<unit>.service/<its id>.
        given = {option: args[args.index(option) + 1] for option in ("--keys", "--krl", "--task", "--login")}
        inside = {f"/run/credentials/{unit}.service/{name}": path for name, path in staged.items()}
        self.checks.append(
            {
                "args": args,
                "input": input,
                "keys": Path(inside[given["--keys"]]).read_text(),
                "krl": Path(inside[given["--krl"]]).read_bytes(),
            }
        )
        if self.check_answer is not None:
            return self.check_answer(args)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cert.pub"
            path.write_text(input)
            shown = subprocess.run(
                ["env", "TZ=UTC", SSH_KEYGEN, "-L", "-f", str(path)], capture_output=True, text=True, check=True
            ).stdout
        lines = [line.strip() for line in shown.splitlines()]
        signer = next(line for line in lines if line.startswith("Signing CA:")).split()[3]
        task_key = next(line for line in lines if line.startswith("Public key:")).split()[3]
        key_id = next(line for line in lines if line.startswith("Key ID:")).split(None, 2)[2].strip('"')
        start = lines.index("Principals:") + 1
        principals = lines[start : next(i for i, line in enumerate(lines) if line.startswith("Critical Options:"))]
        principal = principals[0]
        if signer != fixture_fingerprint(self.checks[-1]["keys"].strip()):
            return subprocess.CompletedProcess(args, 65, "", f"porelo: the certificate is signed by {signer}\n")
        if key_id != f"porelo task {given['--task']} by {given['--login']}":
            return subprocess.CompletedProcess(args, 65, "", f"porelo: the key id {key_id} names another task\n")
        if len(principals) != 1 or principal.split(":")[2:] != [given["--task"]]:
            return subprocess.CompletedProcess(args, 65, "", "porelo: not exactly one principal of this task\n")
        answer = {
            "task": principal.split(":")[2],
            "project": principal.split(":")[1],
            "principal": principal,
            "fingerprint": task_key,
            "signed_by": signer,
        }
        return subprocess.CompletedProcess(args, 0, json.dumps(answer) + "\n", "")

    def open(self, request, timeout):
        url = urlsplit(request.full_url)
        assert (url.scheme, url.hostname, url.port) == ("http", "localhost", None)
        admins = [item["secret"] for item in self.tokens.get(ADMIN, {}).values()]
        assert request.get_header("Authorization") in ["token " + secret for secret in admins]
        method, parts = request.get_method(), url.path.removeprefix("/api/v1/admin/users/").split("/")
        self.requests.append((method, url.path))
        if self.api_failure is not None and parts[0] == self.api_failure:
            raise urllib.error.HTTPError(request.full_url, 500, "fixture failure", {}, io.BytesIO(b""))
        tokens = self.tokens.setdefault(parts[0], {})
        if method == "DELETE":
            del tokens[int(parts[2])]
            data, status = None, 204
        else:
            assert method == "GET" and parts[1] == "tokens", url.path
            query = parse_qs(url.query)
            page, limit = int(query["page"][0]), int(query["limit"][0])
            rows = [{"id": key, "name": item["name"]} for key, item in sorted(tokens.items())]
            data, status = rows[(page - 1) * limit : page * limit], 200
        response = io.BytesIO(b"" if data is None else json.dumps(data).encode())
        response.status = status
        return response


def write(root, name, text, mode=0o600):
    path = root / name.lstrip("/")
    for directory in reversed(path.parents):
        if root in directory.parents:
            directory.mkdir(exist_ok=True)
            directory.chmod(0o700)
    path.write_text(text)
    path.chmod(mode)
    return path


def record(locked=False, member="alpha developer"):
    return f"member={member}\nlocked={str(locked).lower()}\nssh={fixture_key(7)}\nexpires=\n"


@pytest.fixture
def tasks(tmp_path, monkeypatch):
    namespace = runpy.run_path(str(SCRIPT), run_name="task_tests")
    scope = namespace["Host"].__init__.__globals__
    root = tmp_path / "root"
    root.mkdir(mode=0o700)
    keys = Keys(tmp_path / "keys")
    alice, bob = keys.make("alice"), keys.make("bob")
    keys.make("task")
    keys.make("other-task")
    host = namespace["Host"]()
    host.root, host.owner, host.group, host.euid = root, os.getuid(), os.getgid(), 0
    for uid in (1200, 1201):  # The service accounts' user managers, each with its session bus.
        (root / f"run/user/{uid}").mkdir(parents=True, exist_ok=True)
        os.mknod(root / f"run/user/{uid}/bus", stat.S_IFSOCK | 0o600)
    host.sudo_user = "alice"
    host.accounts = {"root": 0, "alice": 1000, "bob": 1001}
    host.groups = set()
    host.commands = {"runuser", "podman", "env", "ssh-keygen", "systemd-run", "porelo"}
    host.now = lambda: NOW
    forge = Forge(scope)
    host.runner = forge.run
    entries = {
        "alice": SimpleNamespace(pw_uid=1000, pw_gid=1000, pw_dir="/home/alice"),
        "bob": SimpleNamespace(pw_uid=1001, pw_gid=1001, pw_dir="/home/bob"),
        "porelo-forge": SimpleNamespace(pw_uid=1200, pw_gid=1200, pw_dir="/home/porelo-forge"),
    }
    monkeypatch.setattr(scope["pwd"], "getpwnam", entries.__getitem__)
    write(
        root,
        "/etc/porelo-host/forge.conf",
        "account=porelo-forge\nhost=host\nagents=codex\nname=forge.example.org\naddress=192.0.2.1\nport=3000\n",
    )
    write(root, "/etc/porelo-host/forge/ca.pem", "fixture CA", 0o644)
    write(root, "/etc/ssh/porelo-revoked.krl", "fixture KRL", 0o644)
    for person in ("alice", "bob"):
        write(root, f"/etc/porelo-host/people/{person}.conf", record())
    applied = {
        "commit": "a" * 40,
        "host_card": {"host": "host"},
        "projects": [],
        "persons": [
            {"login": "alice", "ssh": alice, "expires": None, "revoked": False},
            {"login": "bob", "ssh": bob, "expires": None, "revoked": False},
        ],
        "revoked": [],
    }
    write(root, "/etc/porelo-host/registry/applied.json", json.dumps(applied))
    monkeypatch.setattr(scope["ssl"], "create_default_context", lambda *, cafile: ("CA", cafile))
    monkeypatch.setattr(scope["urllib"].request, "HTTPSHandler", lambda *, context: context)
    monkeypatch.setattr(scope["urllib"].request, "build_opener", lambda *handlers: forge)

    def call(*arguments, data=b"", caller="alice"):
        host.sudo_user = caller
        return namespace["entry"](host, list(arguments), data)

    return SimpleNamespace(
        host=host, forge=forge, keys=keys, call=call, root=root, applied=applied, scope=scope, entries=entries
    )


def snapshot(root):
    return {
        str(path.relative_to(root)): (stat.S_IMODE(path.lstat().st_mode), path.read_bytes() if path.is_file() else None)
        for path in root.rglob("*")
    }


def records(tasks, login="alice"):
    return tasks.root / "var/lib/porelo-host/tasks" / login


def task_certificate(tasks, task="t1", signer="alice", key="task", valid=TODAY, **options):
    """A certificate as Porelo's task start issues it: one principal, its project's, and the key id naming both."""
    options.setdefault("key_id", f"porelo task {task} by {signer}")
    return tasks.keys.certify(signer, key, [f"task:alpha:{task}"], valid, **options)


def no_secret_outside_the_forge(tasks, output):
    """Every token the stand-in forge made lives there alone: no file, no argv, no diagnostic."""
    secrets = tasks.forge.secrets()
    assert secrets
    for path in tasks.root.rglob("*"):
        if path.is_file():
            assert not any(secret.encode() in path.read_bytes() for secret in secrets), f"a token reached {path}"
    assert not any(secret in " ".join(call) for secret in secrets for call in tasks.forge.calls)
    assert not any(secret in output.err for secret in secrets)


def test_a_certificate_signed_by_the_persons_key_is_recorded_and_its_token_answered_once(tasks, capsys):
    """Prevent a task's token from reaching anything but its caller, or a task from starting unrecorded."""
    certificate = task_certificate(tasks)
    assert tasks.call("task", "t1", data=certificate.encode()) == 0
    output = capsys.readouterr()
    token = output.out
    assert [item for item in tasks.forge.tokens["porelo-alice"].values() if item["secret"] == token] == [
        {"name": "porelo-task-t1", "scopes": "write:repository", "secret": token}
    ]
    path = records(tasks) / "t1.json"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    for directory in (path.parent, path.parent.parent):
        assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    recorded = json.loads(path.read_text())
    assert recorded["certificate"] == " ".join(certificate.split()[:2])
    assert recorded["fingerprint"] == tasks.keys.fingerprint("task")
    assert recorded["signed_by"] == tasks.keys.fingerprint("alice")
    assert recorded["principals"] == ["task:alpha:t1"]
    assert (recorded["valid_after"], recorded["valid_before"]) == ("2026-10-30T00:00:00Z", "2026-10-31T00:00:00Z")
    no_secret_outside_the_forge(tasks, output)


@pytest.mark.parametrize(
    "principals, code",
    [
        (["task:default:t1"], 0),
        (["task:alpha:t1"], 0),
        (["task:beta:t1"], 65),
        (["task:hand:t1"], 65),
        (["task:t1"], 65),
        (["task:alpha:t1", "task:beta:t1"], 65),
        (["task:Alpha:t1"], 65),
        (["task::t1"], 65),
        (["task:alpha:t2"], 65),
        (["task:alpha:t1", "alice"], 65),
    ],
    ids=[
        "default",
        "member",
        "not a member",
        "hand admission",
        "old form",
        "two",
        "invalid project",
        "empty project",
        "other task",
        "a second principal",
    ],
)
def test_a_task_names_exactly_one_principal_by_its_project(tasks, capsys, principals, code):
    """Prevent a certificate naming no project, two projects or another task from starting this task."""
    certificate = tasks.keys.certify("alice", "task", principals, TODAY, key_id="porelo task t1 by alice")
    assert tasks.call("task", "t1", data=certificate.encode()) == code
    capsys.readouterr()
    assert (records(tasks) / "t1.json").exists() == (code == 0)
    assert (tasks.forge.checks != []) == (code == 0), "the host refuses these itself, before Porelo's check"


@pytest.mark.parametrize(
    "case, code",
    [
        ("another signer", 65),
        ("another task", 65),
        ("expired", 65),
        ("not yet valid", 65),
        ("without an end", 65),
        ("host certificate", 65),
        ("bad signature", 65),
        ("revoked person", 65),
        ("person not in the registry", 65),
        ("plain key", 64),
        ("too long", 64),
        ("two lines", 64),
        ("empty", 64),
    ],
)
def test_a_certificate_the_persons_current_key_did_not_sign_for_this_task_now_is_refused_before_anything_is_written(
    tasks, capsys, case, code
):
    """Prevent a task token for a certificate someone else signed, for another task, or outside its lifetime."""
    data = {
        "another signer": lambda: task_certificate(tasks, signer="bob"),
        "another task": lambda: task_certificate(tasks, task="t2"),
        "expired": lambda: task_certificate(tasks, valid="20261029000000Z:20261030115959Z"),
        "not yet valid": lambda: task_certificate(tasks, valid="20261030120001Z:20261031000000Z"),
        "without an end": lambda: task_certificate(tasks, valid="20261030000000Z:forever"),
        "host certificate": lambda: task_certificate(tasks, host=True),
        "bad signature": lambda: tampered(task_certificate(tasks)),
        "revoked person": lambda: revoke(tasks) or task_certificate(tasks),
        "person not in the registry": lambda: forget(tasks) or task_certificate(tasks),
        "plain key": lambda: (tasks.keys.directory / "task.pub").read_text(),
        "too long": lambda: task_certificate(tasks).strip() + " " + "x" * 16384 + "\n",
        "two lines": lambda: task_certificate(tasks) * 2,
        "empty": lambda: "",
    }[case]().encode()
    before = snapshot(tasks.root)
    assert tasks.call("task", "t1", data=data) == code
    output = capsys.readouterr()
    assert output.out == "" and output.err.startswith("porelo-host-person: ")
    assert snapshot(tasks.root) == before
    assert not any("generate-access-token" in call for call in tasks.forge.calls)
    assert tasks.forge.requests == []


def tampered(certificate):
    kind, blob = certificate.split()[:2]
    raw = bytearray(base64.b64decode(blob))
    raw[-5] ^= 1
    return kind + " " + base64.b64encode(raw).decode() + "\n"


def revoke(tasks):
    tasks.applied["revoked"] = ["alice"]
    tasks.applied["persons"][0]["revoked"] = True
    write(tasks.root, "/etc/porelo-host/registry/applied.json", json.dumps(tasks.applied))


def forget(tasks):
    tasks.applied["persons"] = tasks.applied["persons"][1:]
    write(tasks.root, "/etc/porelo-host/registry/applied.json", json.dumps(tasks.applied))


def test_the_same_certificate_again_replaces_its_token_and_another_for_a_recorded_task_is_refused(tasks, capsys):
    """Prevent a recorded certificate from being replaced, or a retried start from leaving two tokens for one task."""
    certificate = task_certificate(tasks)
    assert tasks.call("task", "t1", data=certificate.encode()) == 0
    first = capsys.readouterr().out
    assert tasks.call("task", "t1", data=certificate.encode()) == 0
    second = capsys.readouterr().out
    assert first != second
    assert tasks.forge.named("porelo-alice") == ["porelo-task-t1"]
    assert [item["secret"] for item in tasks.forge.tokens["porelo-alice"].values()] == [second]
    before = (records(tasks) / "t1.json").read_bytes()
    other = task_certificate(tasks, key="other-task")
    assert tasks.call("task", "t1", data=other.encode()) == 65
    assert "recorded" in capsys.readouterr().err
    assert (records(tasks) / "t1.json").read_bytes() == before
    assert [item["secret"] for item in tasks.forge.tokens["porelo-alice"].values()] == [second]


def test_a_task_key_recorded_for_one_task_is_refused_for_another(tasks, capsys):
    """Prevent two task certificates from making a trace by their key's fingerprint ambiguous."""
    assert tasks.call("task", "t1", data=task_certificate(tasks).encode()) == 0
    capsys.readouterr()
    assert tasks.call("task", "t2", data=task_certificate(tasks, task="t2").encode()) == 65
    assert "t2" not in str(list(records(tasks).iterdir()))
    assert tasks.forge.named("porelo-alice") == ["porelo-task-t1"]


def test_task_end_deletes_that_tasks_token_alone(tasks, capsys):
    """Prevent an ended task's token from staying usable, or an end from taking another task's or the person's."""
    assert tasks.call("task", "t1", data=task_certificate(tasks).encode()) == 0
    assert tasks.call("task", "t2", data=task_certificate(tasks, task="t2", key="other-task").encode()) == 0
    assert tasks.call("forge-token") == 0
    capsys.readouterr()
    assert tasks.call("task", "--end", "t1") == 0
    assert json.loads(capsys.readouterr().out) == {"task": "t1", "ended": True}
    assert tasks.forge.named("porelo-alice") == ["porelo-task-t2"]
    assert len(tasks.forge.named("alice")) == 1
    assert (records(tasks) / "t1.json").is_file(), "the record outlives its token"
    assert tasks.call("task", "--end", "t9") == 65


def test_show_answers_a_recorded_certificate_to_any_admitted_person_and_changes_nothing(tasks, capsys):
    """Prevent a plain-key signature from losing its certificate once the task key is gone, or show from changing it."""
    certificate = task_certificate(tasks)
    assert tasks.call("task", "t1", data=certificate.encode()) == 0
    capsys.readouterr()
    before = snapshot(tasks.root)
    calls = len(tasks.forge.calls)
    assert tasks.call("task", "--show", tasks.keys.fingerprint("task"), caller="bob") == 0
    answer = json.loads(capsys.readouterr().out)
    assert answer["certificate"] == " ".join(certificate.split()[:2])
    assert answer["login"] == "alice" and answer["task"] == "t1"
    assert tasks.call("task", "--show", tasks.keys.fingerprint("task"), caller=None) == 0
    capsys.readouterr()
    assert tasks.call("task", "--show", tasks.keys.fingerprint("other-task"), caller="bob") == 65
    write(tasks.root, "/etc/porelo-host/people/bob.conf", record(locked=True))
    before["etc/porelo-host/people/bob.conf"] = snapshot(tasks.root)["etc/porelo-host/people/bob.conf"]
    assert tasks.call("task", "--show", tasks.keys.fingerprint("task"), caller="bob") == 65
    assert snapshot(tasks.root) == before
    assert len(tasks.forge.calls) == calls


def test_the_sweep_deletes_the_tokens_of_expired_tasks_alone(tasks, capsys):
    """Prevent a task token from outliving its certificate, or the sweep from taking a running task's token."""
    early = "20261030000000Z:20261030130000Z"
    assert tasks.call("task", "t1", data=task_certificate(tasks, valid=early).encode()) == 0
    assert tasks.call("task", "t2", data=task_certificate(tasks, task="t2", key="other-task").encode()) == 0
    assert tasks.call("forge-token") == 0
    capsys.readouterr()
    tasks.host.now = lambda: NOW + datetime.timedelta(hours=1)
    assert tasks.call("sweep", caller=None) == 0
    assert json.loads(capsys.readouterr().out) == {"swept": ["alice/t1"]}
    assert tasks.forge.named("porelo-alice") == ["porelo-task-t2"]
    assert len(tasks.forge.named("alice")) == 1
    assert tasks.call("sweep", caller=None) == 0
    assert json.loads(capsys.readouterr().out) == {"swept": []}
    assert tasks.call("sweep", caller="alice") == 65


def test_the_sweep_goes_on_past_one_persons_forge_failure_and_names_it(tasks, capsys):
    """Prevent one broken forge user from keeping every other person's expired task tokens alive."""
    early = "20261030000000Z:20261030130000Z"
    assert tasks.call("task", "t1", data=task_certificate(tasks, valid=early).encode()) == 0
    bob_task = tasks.keys.certify("bob", "other-task", ["task:alpha:b1"], early, key_id="porelo task b1 by bob")
    assert tasks.call("task", "b1", data=bob_task.encode(), caller="bob") == 0
    capsys.readouterr()
    tasks.host.now = lambda: NOW + datetime.timedelta(hours=1)
    tasks.forge.api_failure = "porelo-alice"
    assert tasks.call("sweep", caller=None) == 69
    output = capsys.readouterr()
    assert "alice" in output.err and output.out == ""
    assert tasks.forge.named("porelo-bob") == []


def test_forge_token_replaces_the_persons_one_token_and_answers_it_alone(tasks, capsys):
    """Prevent a second lasting token of the person, or their token reaching a file, an argument or a log."""
    assert tasks.call("forge-token") == 0
    first = capsys.readouterr()
    assert tasks.call("forge-token") == 0
    second = capsys.readouterr()
    tokens = list(tasks.forge.tokens["alice"].values())
    assert [item["secret"] for item in tokens] == [second.out] and first.out != second.out
    assert tokens[0]["scopes"] == "write:repository,write:issue,write:organization,read:user"
    assert len(second.out) == 40 and second.err == ""
    no_secret_outside_the_forge(tasks, second)


@pytest.mark.parametrize(
    "caller, change, code",
    [(None, None, 64), ("alice", "locked", 65), ("alice", "revoked", 65), ("carol", None, 65)],
)
def test_forge_token_is_refused_to_root_a_locked_revoked_or_unknown_person(tasks, capsys, caller, change, code):
    """Prevent a token for someone the host locked or the registry revoked, or one root could hand to anyone."""
    if change == "locked":
        write(tasks.root, "/etc/porelo-host/people/alice.conf", record(locked=True))
    elif change == "revoked":
        revoke(tasks)
    assert tasks.call("forge-token", caller=caller) == code
    assert capsys.readouterr().out == ""
    assert tasks.forge.calls == []


@pytest.mark.parametrize(
    "args",
    [
        ("forge-token", "alice"),
        ("task",),
        ("task", "T1"),
        ("task", "../t1"),
        ("task", "t1", "extra"),
        ("task", "--end"),
        ("task", "--show", "SHA256:short"),
        ("task", "--drop", "t1"),
        ("sweep", "now"),
    ],
)
def test_wrong_task_and_token_calls_change_nothing(tasks, capsys, args):
    """Prevent a malformed call from reaching the forge or the records."""
    before = snapshot(tasks.root)
    assert tasks.call(*args, data=task_certificate(tasks).encode()) == 64
    assert capsys.readouterr().out == ""
    assert snapshot(tasks.root) == before
    assert tasks.forge.calls == []


def test_a_task_is_recorded_without_a_token_where_the_host_runs_no_forge(tasks, capsys):
    """Keep the certificate's trace on a host without a forge, and make no token there."""
    write(tasks.root, "/etc/porelo-host/forge.conf", "host=host\n")
    assert tasks.call("task", "t1", data=task_certificate(tasks).encode()) == 0
    assert capsys.readouterr().out == ""
    assert (records(tasks) / "t1.json").is_file()
    assert not any("podman" in call for call in tasks.forge.calls)
    assert tasks.call("forge-token") == 69


@pytest.mark.parametrize("part", ["root", "person", "record"])
def test_task_record_links_cannot_redirect_root_writes_or_reads(tasks, tmp_path, capsys, part):
    """Prevent a linked task directory or record from redirecting root into another person's files."""
    certificate = task_certificate(tasks)
    assert tasks.call("task", "t1", data=certificate.encode()) == 0
    capsys.readouterr()
    outside = tmp_path / "outside"
    outside.mkdir(mode=0o700)
    sentinel = outside / "sentinel"
    sentinel.write_text("untouched")
    target = {"root": records(tasks).parent, "person": records(tasks), "record": records(tasks) / "t1.json"}[part]
    saved = target.with_name(target.name + ".saved")
    target.rename(saved)
    target.symlink_to(sentinel if part == "record" else outside)
    calls = len(tasks.forge.calls)
    assert tasks.call("task", "t1", data=certificate.encode()) == 73
    assert capsys.readouterr().out == ""
    assert sentinel.read_text() == "untouched"
    assert [call[0] for call in tasks.forge.calls[calls:]] == ["env", "systemd-run"], "only the checks run"


def test_a_rotated_registry_key_cannot_authorize_the_previous_keys_certificate(tasks, capsys):
    """Prevent a certificate signed by a superseded person key from obtaining a task token."""
    certificate = task_certificate(tasks)
    tasks.applied["persons"][0]["ssh"] = tasks.keys.make("replacement")
    write(tasks.root, "/etc/porelo-host/registry/applied.json", json.dumps(tasks.applied))
    before = snapshot(tasks.root)
    assert tasks.call("task", "t1", data=certificate.encode()) == 65
    assert capsys.readouterr().out == ""
    assert snapshot(tasks.root) == before
    assert tasks.forge.requests == []


@pytest.mark.parametrize("caller", [None, "alice"])
def test_no_caller_can_request_a_named_person_token(tasks, capsys, caller):
    """Leave no verb that mints another person's token; each person asks for their own through sudo."""
    assert tasks.call("forge-token", "--for", "bob", caller=caller) == 64
    assert capsys.readouterr().out == ""
    assert tasks.forge.calls == []


def test_porelo_judges_the_certificate_against_the_key_in_force_and_the_krl_before_any_record(tasks, capsys):
    """Prevent a task recorded on the host's own reading alone, without Porelo's check of the same certificate."""
    certificate = task_certificate(tasks)
    assert tasks.call("task", "t1", data=certificate.encode()) == 0
    capsys.readouterr()
    [check] = tasks.forge.checks
    args = check["args"]
    assert args[: args.index("porelo")][:5] == ["systemd-run", "--pipe", "--wait", "--quiet", "--collect"]
    for setting in ("DynamicUser=yes", "PrivateNetwork=yes", "ProtectHome=yes"):
        assert args[args.index(setting) - 1] == "-p"
    credentials = "/run/credentials/porelo-host-task-check.service"
    assert args[args.index("porelo") :] == [
        "porelo",
        "task",
        "check-certificate",
        "--task",
        "t1",
        "--login",
        "alice",
        "--keys",
        f"{credentials}/keys",
        "--krl",
        f"{credentials}/revoked.krl",
        "--json",
    ]
    assert check["input"] == " ".join(certificate.split()[:2]) + "\n"
    assert check["keys"] == tasks.applied["persons"][0]["ssh"] + "\n"
    assert check["krl"] == b"fixture KRL"
    assert list((tasks.root / "run/porelo-host/sync").iterdir()) == [], "the staged keys and KRL are removed"
    assert tasks.forge.calls.index(args) < next(
        index for index, call in enumerate(tasks.forge.calls) if "generate-access-token" in call
    )


@pytest.mark.parametrize(
    "answer, code, words",
    [
        (
            lambda args: subprocess.CompletedProcess(args, 65, "", "porelo: the key id names another login\n"),
            65,
            "the key id names another login",
        ),
        ({"fingerprint": "SHA256:" + "A" * 43}, 69, "another certificate"),
        ({"signed_by": "SHA256:" + "A" * 43}, 69, "another certificate"),
        ({"project": "default"}, 69, "another certificate"),
        (lambda args: subprocess.CompletedProcess(args, 0, "not json", ""), 69, "no valid JSON"),
    ],
    ids=["refused", "another task key", "another signer", "another project", "no answer"],
)
def test_a_certificate_porelo_refuses_or_answers_otherwise_starts_no_task(tasks, capsys, answer, code, words):
    """Prevent a task token for a certificate Porelo's check refused, or for one it did not judge."""
    if isinstance(answer, dict):
        changed = answer
        tasks.forge.check_answer = lambda args: subprocess.CompletedProcess(
            args,
            0,
            json.dumps(
                {
                    "fingerprint": tasks.keys.fingerprint("task"),
                    "signed_by": tasks.keys.fingerprint("alice"),
                    "project": "alpha",
                    **changed,
                }
            ),
            "",
        )
    else:
        tasks.forge.check_answer = answer
    assert tasks.call("task", "t1", data=task_certificate(tasks).encode()) == code
    output = capsys.readouterr()
    assert output.out == "" and words in output.err
    assert not (records(tasks) / "t1.json").exists()
    assert not any("generate-access-token" in call for call in tasks.forge.calls)


@pytest.mark.parametrize(
    "change, words",
    [
        ("missing", "is missing"),
        ("a link", "not a plain file"),
        ("writable by others", "not a plain file"),
        ("unreadable", "cannot read"),
    ],
)
def test_a_missing_krl_refuses_the_task_before_porelo_runs(tasks, capsys, change, words):
    """Prevent a certificate judged without the revocations in force, or against a KRL root does not hold alone."""
    krl = tasks.root / "etc/ssh/porelo-revoked.krl"
    if change == "missing":
        krl.unlink()
    elif change == "a link":
        krl.rename(krl.with_name("elsewhere.krl"))
        krl.symlink_to("elsewhere.krl")
    elif change == "writable by others":
        krl.chmod(0o666)
    else:
        krl.chmod(0o200)
    assert tasks.call("task", "t1", data=task_certificate(tasks).encode()) == 69
    error = capsys.readouterr().err
    assert words in error and "porelo-revoked.krl" in error
    assert tasks.forge.checks == [] and not (records(tasks) / "t1.json").exists()


@pytest.mark.parametrize("member", ["hand", "beta developer", "alphabet developer"])
def test_a_certificate_for_a_project_the_person_is_no_member_of_is_refused_before_porelo_runs(tasks, capsys, member):
    """Prevent a person's task token for another project's task, which the host checks itself."""
    write(tasks.root, "/etc/porelo-host/people/alice.conf", record(member=member))
    certificate = tasks.keys.certify("alice", "task", ["task:alpha:t1"], TODAY, key_id="porelo task t1 by alice")
    assert tasks.call("task", "t1", data=certificate.encode()) == 65
    assert "no member" in capsys.readouterr().err
    assert tasks.forge.checks == []


def test_a_project_admin_starts_a_task_of_their_project(tasks, capsys):
    """Prevent the membership check from reading a project admin's record as no membership."""
    write(tasks.root, "/etc/porelo-host/people/alice.conf", record(member="alpha project-admin"))
    assert tasks.call("task", "t1", data=task_certificate(tasks).encode()) == 0
    capsys.readouterr()
    assert (records(tasks) / "t1.json").exists()


@pytest.mark.parametrize("command", ["porelo", "systemd-run"])
def test_no_porelo_on_the_host_refuses_the_task_as_unprepared(tasks, capsys, command):
    """Prevent root from running a porelo or systemd-run it has not checked as root's alone."""
    tasks.host.commands.discard(command)
    assert tasks.call("task", "t1", data=task_certificate(tasks).encode()) == 69
    capsys.readouterr()
    assert tasks.forge.checks == [] and not (records(tasks) / "t1.json").exists()


PUSH_HOOK = "/usr/local/libexec/porelo/pre-receive"
REPOSITORY = "/var/lib/gitea/git/repositories/alpha/app.git"
QUARANTINE = REPOSITORY + "/objects/tmp_objdir-incoming-AbC123"
VOLUME = "/home/porelo-forge/.local/share/containers/storage/volumes/forgejo-data/_data"
HOOK_LINES = "a" * 40 + " " + "c" * 40 + " refs/heads/main\n"


def judged_project(tasks):
    """Project alpha registered, alice's key in force as its one signer, the push's quarantine in the forge's volume."""
    write(
        tasks.root,
        "/etc/porelo-host/projects/alpha.conf",
        f"admin=alice\nsigned_by={tasks.applied['persons'][0]['ssh']}\npublisher=porelo-publisher-alpha\n",
    )
    current = {"alice": {"ssh": tasks.applied["persons"][0]["ssh"], "expires": None}}
    write(tasks.root, "/etc/porelo-host/signers/alpha.json", json.dumps({"current": current, "history": []}))
    # The forge's volume is the test's own, so the forge account is the test's uid.
    tasks.entries["porelo-forge"].pw_uid = os.getuid()
    bus = tasks.root / f"run/user/{os.getuid()}/bus"
    bus.parent.mkdir(parents=True, exist_ok=True)
    os.mknod(bus, stat.S_IFSOCK | 0o600)
    (tasks.root / (VOLUME + QUARANTINE.removeprefix("/var/lib/gitea")).lstrip("/")).mkdir(parents=True)


def push_request(fields=None, lines=HOOK_LINES, headers=None, extra=""):
    values = {
        "repository": REPOSITORY,
        "quarantine": QUARANTINE,
        "objects": QUARANTINE,
        "alternates": REPOSITORY + "/objects",
        **(fields or {}),
    }
    body = "".join(f"{key} {value}\n" for key, value in values.items()) + "\n" + lines
    data = body.encode()
    head = (headers if headers is not None else f"Content-Length: {len(data)}\r\n") + extra
    return f"POST /verify HTTP/1.1\r\nHost: localhost\r\n{head}\r\n".encode() + data


class Hook:
    """The forge hook's end of the socket: what it sent, what it was answered, and whose peer it is."""

    def __init__(self, request, uid=None):
        self.request, self.answer, self.timeout = request, b"", None
        self.uid = os.getuid() if uid is None else uid

    def settimeout(self, timeout):
        self.timeout = timeout

    def recv(self, size):
        assert self.timeout == 30, "a read of the hook's request is never without a bound"
        chunk, self.request = self.request[:size], self.request[size:]
        return chunk

    def getsockopt(self, level, option, size):
        return struct.pack("iII", 4242, self.uid, self.uid)

    def sendall(self, data):
        self.answer += data

    def status(self):
        return int(self.answer.split(b" ", 2)[1])

    def text(self):
        return self.answer.partition(b"\r\n\r\n")[2].decode()


def arrivals(tasks, repository="app"):
    path = tasks.root / f"var/lib/porelo-host/arrivals/alpha/{repository}.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def judge(tasks, request=None, uid=None):
    hook = Hook(push_request() if request is None else request, uid=uid)
    assert tasks.call("verify-push", data=hook, caller=None) == 0
    return hook


def test_a_push_porelo_accepts_is_recorded_with_its_signer_and_answered_200(tasks, capsys):
    """Prevent a push judged on what the hook claims, or an accepted commit left without its verdict."""
    judged_project(tasks)
    hook = judge(tasks)
    capsys.readouterr()
    assert hook.status() == 200, hook.text()
    [verify] = tasks.forge.verifies
    args = verify["args"]
    host = str(tasks.root) + VOLUME + "/git/repositories/alpha/app.git"
    for setting in (
        f"User=porelo-forge",
        "PrivateNetwork=yes",
        "PrivateTmp=yes",
        "ProtectHome=tmpfs",
        "ProtectSystem=strict",
        "NoNewPrivileges=yes",
        "RuntimeMaxSec=270",
        f"BindReadOnlyPaths={host}",
        "Environment=HOME=/tmp",
        f"Environment=GIT_QUARANTINE_PATH={host}/objects/tmp_objdir-incoming-AbC123",
        f"Environment=GIT_OBJECT_DIRECTORY={host}/objects/tmp_objdir-incoming-AbC123",
        f"Environment=GIT_ALTERNATE_OBJECT_DIRECTORIES={host}/objects",
    ):
        assert args[args.index(setting) - 1] == "-p", setting
    assert args[args.index("porelo") : args.index("porelo") + 5] == ["porelo", "commit", "verify", "--repository", host]
    assert tasks.forge.timeouts[-1] == 280
    assert verify["input"] == HOOK_LINES
    key = tasks.applied["persons"][0]["ssh"]
    assert verify["given"]["--signers"] == f'alice namespaces="git" {key}\n'.encode()
    assert verify["given"]["--certifiers"] == f'task:alpha:* cert-authority,namespaces="git" {key}\n'.encode()
    assert verify["given"]["--krl"] == b"fixture KRL"
    assert arrivals(tasks) == [
        {
            "commit": "c" * 40,
            "ref": "refs/heads/main",
            "verdict": "accepted",
            "arrived": "2026-10-30T12:00:00Z",
            "signer": {"kind": "person", "fingerprint": "SHA256:" + "B" * 43},
        }
    ]
    record = tasks.root / "var/lib/porelo-host/arrivals/alpha/app.jsonl"
    assert stat.S_IMODE(record.stat().st_mode) == 0o600
    assert list((tasks.root / "run/porelo-host/push").iterdir()) == []


def test_an_expired_card_signs_nothing_and_certifies_no_task(tasks, capsys):
    """Prevent a person whose card has ended from signing a commit the host takes."""
    judged_project(tasks)
    current = {
        "alice": {"ssh": tasks.applied["persons"][0]["ssh"], "expires": "2026-10-29"},
        "bob": {"ssh": tasks.applied["persons"][1]["ssh"], "expires": None},
    }
    write(tasks.root, "/etc/porelo-host/signers/alpha.json", json.dumps({"current": current, "history": []}))
    judge(tasks)
    given = tasks.forge.verifies[-1]["given"]
    assert given["--signers"] == f'bob namespaces="git" {tasks.applied["persons"][1]["ssh"]}\n'.encode()
    assert tasks.applied["persons"][0]["ssh"].encode() not in given["--certifiers"]


def test_only_the_projects_task_certificates_valid_now_reach_porelo(tasks, capsys):
    """Prevent a plain task key of another project, or one whose certificate ended, from signing for this one."""
    judged_project(tasks)
    assert tasks.call("task", "t1", data=task_certificate(tasks).encode()) == 0
    capsys.readouterr()
    assert tasks.call("task", "--show", tasks.keys.fingerprint("task"), caller=None) == 0
    shown = capsys.readouterr().out
    directory = records(tasks)
    entry = json.loads((directory / "t1.json").read_text())
    for name, changes in (
        ("t2", {"principals": ["task:beta:t2"]}),
        ("t3", {"valid_before": "2026-10-30T11:59:59Z"}),
        ("t4", {"valid_after": "2026-10-30T12:00:01Z"}),
    ):
        path = directory / f"{name}.json"
        path.write_text(json.dumps({**entry, **changes, "task": name}))
        path.chmod(0o600)
    judge(tasks)
    assert tasks.forge.verifies[-1]["given"]["--certificates"] == shown.encode()


def test_a_push_porelo_refuses_is_answered_403_with_its_lines_and_recorded_nowhere(tasks, capsys):
    """Prevent a refused commit reaching the forge, or its reason being lost to the pusher."""
    judged_project(tasks)
    tasks.forge.verify_answer = lambda args: subprocess.CompletedProcess(
        args, 65, "", "c" * 40 + " signed by a revoked key\n\x1b[31mcolour\n"
    )
    hook = judge(tasks)
    capsys.readouterr()
    assert hook.status() == 403
    assert hook.text() == "porelo: " + "c" * 40 + " signed by a revoked key\n"
    assert arrivals(tasks) == []


@pytest.mark.parametrize(
    "answer",
    [
        lambda args: subprocess.CompletedProcess(args, 1, "", "crash"),
        lambda args: subprocess.CompletedProcess(args, 0, "not json", ""),
        lambda args: subprocess.CompletedProcess(args, 0, json.dumps({"accepted": False, "commits": []}), ""),
        lambda args: subprocess.CompletedProcess(
            args, 0, json.dumps({"checked_at": "x", "accepted": True, "commits": [{"commit": "nope"}]}), ""
        ),
        lambda args: subprocess.CompletedProcess(
            args,
            0,
            json.dumps(
                {
                    "checked_at": "x",
                    "accepted": True,
                    "commits": [{"commit": "c" * 40, "verdict": "refused", "signer": {}}],
                }
            ),
            "",
        ),
        lambda args: subprocess.CompletedProcess(
            args,
            0,
            json.dumps(
                {
                    "checked_at": "yesterdayZ",
                    "accepted": True,
                    "commits": [
                        {"commit": "c" * 40, "verdict": "accepted", "signer": {"fingerprint": "SHA256:" + "B" * 43}}
                    ],
                }
            ),
            "",
        ),
        lambda args: subprocess.CompletedProcess(
            args,
            0,
            json.dumps(
                {
                    "checked_at": "2026-10-30T12:00:00Z",
                    "accepted": True,
                    "commits": [{"commit": "c" * 40, "verdict": "accepted", "signer": {"fingerprint": "nope"}}],
                }
            ),
            "",
        ),
    ],
    ids=["crash", "no json", "not accepted", "broken commit", "a refused verdict", "no time", "no signer"],
)
def test_any_other_answer_of_porelo_refuses_the_push(tasks, capsys, answer):
    """Prevent a push from passing when Porelo did not say every commit holds."""
    judged_project(tasks)
    tasks.forge.verify_answer = answer
    hook = judge(tasks)
    capsys.readouterr()
    assert hook.status() == 500 and arrivals(tasks) == []


@pytest.mark.parametrize(
    "missing, setup",
    [
        ("porelo", lambda tasks: tasks.host.commands.discard("porelo")),
        ("systemd-run", lambda tasks: tasks.host.commands.discard("systemd-run")),
        ("KRL", lambda tasks: (tasks.root / "etc/ssh/porelo-revoked.krl").unlink()),
        ("KRL", lambda tasks: (tasks.root / "etc/ssh/porelo-revoked.krl").chmod(0o200)),
        ("signers", lambda tasks: (tasks.root / "etc/porelo-host/signers/alpha.json").unlink()),
    ],
    ids=["no porelo", "no systemd-run", "no KRL", "unreadable KRL", "no signers"],
)
def test_a_host_unready_to_judge_refuses_the_push_unjudged(tasks, capsys, missing, setup):
    """Prevent a push from passing, or Porelo from running, without everything a judgement needs."""
    judged_project(tasks)
    setup(tasks)
    hook = judge(tasks)
    capsys.readouterr()
    assert hook.status() == 500, missing
    assert tasks.forge.verifies == [] and arrivals(tasks) == []


def test_a_push_that_only_deletes_refs_passes_unjudged_and_unrecorded(tasks, capsys):
    """Prevent a branch deletion, which brings no quarantine, from being refused or recorded as a commit."""
    judged_project(tasks)
    deletion = push_request(
        {"quarantine": "", "objects": "", "alternates": ""}, lines="c" * 40 + " " + "0" * 40 + " refs/heads/old\n"
    )
    hook = judge(tasks, deletion)
    capsys.readouterr()
    assert hook.status() == 200 and tasks.forge.verifies == [] and arrivals(tasks) == []
    (tasks.root / "etc/porelo-host/projects/alpha.conf").unlink()
    assert judge(tasks, deletion).status() == 403, "a deletion in an unregistered project's repository passes"


def test_a_push_mixing_a_deletion_with_an_update_is_judged(tasks, capsys):
    """Prevent an unsigned update from passing unjudged beside a ref deletion in the same push."""
    judged_project(tasks)
    lines = "c" * 40 + " " + "0" * 40 + " refs/heads/old\n" + HOOK_LINES
    hook = judge(tasks, push_request(lines=lines))
    capsys.readouterr()
    assert hook.status() == 200 and [verify["input"] for verify in tasks.forge.verifies] == [lines]


def test_the_forge_without_the_organization_s_directory_arms_nothing(tasks, capsys):
    """Prevent a project whose organization holds no repository yet from failing its sync."""
    forge_repository(tasks, "app", ["d" * 40], project="beta")
    assert tasks.host.arm_pushes("alpha") == [] and arrivals(tasks) == []


@pytest.mark.parametrize(
    "fields, uid",
    [
        ({}, os.getuid() + 1),
        ({"repository": "/var/lib/gitea/git/repositories/alice/app.git"}, None),
        (
            {
                "repository": "/var/lib/gitea/git/repositories/beta/app.git",
                "quarantine": "/var/lib/gitea/git/repositories/beta/app.git/objects/incoming-x",
                "objects": "/var/lib/gitea/git/repositories/beta/app.git/objects/incoming-x",
                "alternates": "/var/lib/gitea/git/repositories/beta/app.git/objects",
            },
            None,
        ),
        ({"repository": "/var/lib/gitea/git/repositories/alpha/../beta/app.git"}, None),
        ({"quarantine": "/var/lib/gitea/git/repositories/beta/app.git/objects/incoming-x"}, None),
        ({"objects": REPOSITORY + "/objects"}, None),
        ({"alternates": "/var/lib/gitea/git/repositories/beta/app.git/objects"}, None),
        ({"quarantine": REPOSITORY + "/objects/incoming-Gone", "objects": REPOSITORY + "/objects/incoming-Gone"}, None),
        ({"extra": "1"}, None),
    ],
    ids=[
        "another peer",
        "other quarantine of a project",
        "unregistered project",
        "dot dot",
        "other quarantine",
        "objects",
        "other alternates",
        "no such quarantine",
        "extra field",
    ],
)
def test_a_request_not_from_the_forge_or_not_of_one_project_repository_is_refused_unjudged(tasks, capsys, fields, uid):
    """Prevent anyone but the forge's hook, or a path outside the pushed repository, from reaching Porelo or a record."""
    judged_project(tasks)
    write(
        tasks.root,
        "/etc/porelo-host/projects/alice.conf",
        f"admin=alice\nsigned_by={tasks.applied['persons'][0]['ssh']}\npublisher=porelo-publisher-alpha\n",
    )
    hook = judge(tasks, push_request(fields), uid=uid)
    capsys.readouterr()
    assert hook.status() == 403, hook.text()
    assert tasks.forge.verifies == [] and arrivals(tasks) == []


@pytest.mark.parametrize("link", ["git", "repositories", "alpha", "app.git", "objects", "tmp_objdir-incoming-AbC123"])
def test_a_link_on_the_way_to_the_quarantine_is_refused_unjudged(tasks, capsys, link):
    """Prevent a link in the forge's volume from turning the judged objects into others the hook did not name."""
    judged_project(tasks)
    path = tasks.root / (VOLUME + QUARANTINE.removeprefix("/var/lib/gitea")).lstrip("/")
    while path.name != link:
        path = path.parent
    moved = path.with_name(path.name + ".real")
    path.rename(moved)
    path.symlink_to(moved)
    hook = judge(tasks)
    capsys.readouterr()
    assert hook.status() == 403 and tasks.forge.verifies == []


@pytest.mark.parametrize(
    "request_",
    [
        push_request(extra="Transfer-Encoding: chunked\r\n"),
        push_request(extra=f"Content-Length: {len(push_request().partition(b'\r\n\r\n')[2])}\r\n"),
        push_request(headers="Content-Length: +5\r\n"),
        push_request(headers="Content-Length: 0\r\n"),
        push_request(headers="Broken header\r\n"),
        push_request(lines=""),
        push_request(lines="not an update\n"),
        push_request(lines=HOOK_LINES + "\n"),
        push_request().replace(b"\n\n" + HOOK_LINES.encode(), b"\n" + HOOK_LINES.encode()),
        b"GET /verify HTTP/1.1\r\n\r\n",
        b"POST /verify HTTP/1.1\r\n",
    ],
    ids=[
        "chunked",
        "two lengths",
        "signed length",
        "no body",
        "broken header",
        "no update",
        "bad update",
        "empty update",
        "no separator",
        "another request",
        "cut short",
    ],
)
def test_a_malformed_request_is_refused_unjudged(tasks, capsys, request_):
    """Prevent a request the judge could read otherwise than the hook meant from reaching Porelo."""
    judged_project(tasks)
    hook = judge(tasks, request_)
    capsys.readouterr()
    assert hook.status() == 403 and tasks.forge.verifies == []


def test_verify_push_runs_for_the_socket_alone_never_through_sudo(tasks, capsys):
    """Prevent a person from writing a verdict through sudo."""
    assert tasks.call("verify-push", data=Hook(push_request())) == 65
    capsys.readouterr()


def forge_repository(tasks, name, history, project="alpha", hook=True):
    """A bare repository in the stand-in forge's data, Forgejo's own pre-receive hook in it and its history listed."""
    tasks.forge.gitea = tasks.root.parent / "gitea"
    (tasks.forge.gitea / "git/repositories").mkdir(parents=True, exist_ok=True)
    repository = tasks.forge.gitea / f"git/repositories/{project}/{name}.git"
    (repository / "hooks").mkdir(parents=True)
    if hook:
        (repository / "hooks/pre-receive").write_text("#!/bin/sh\n")
        (repository / "hooks/pre-receive").chmod(0o755)
    if history is not None:
        (repository / "history").write_text("".join(commit + "\n" for commit in history))
    return repository


def test_sync_arms_each_repository_and_records_its_history_as_migrated_once(tasks, capsys):
    """Prevent migrated history judged as an arrival, a repository left unjudged, or its history recorded twice."""
    app = forge_repository(tasks, "app", ["d" * 40, "e" * 40, "d" * 40])
    dot = forge_repository(tasks, ".hidden", ["f" * 40])
    assert tasks.host.arm_pushes("alpha") == [".hidden", "app"]
    for repository in (app, dot):
        assert os.readlink(repository / "hooks/pre-receive.d/porelo") == str(tasks.forge.gitea / "pre-receive-hook")
    assert arrivals(tasks) == [
        {"commit": "d" * 40, "verdict": "migrated", "arrived": "2026-10-30T12:00:00Z"},
        {"commit": "e" * 40, "verdict": "migrated", "arrived": "2026-10-30T12:00:00Z"},
        {"verdict": "armed", "arrived": "2026-10-30T12:00:00Z"},
    ]
    assert tasks.host.arm_pushes("alpha") == []
    assert len(arrivals(tasks)) == 3


def test_a_repository_armed_but_unrecorded_is_listed_again_and_its_arrivals_kept_once(tasks, capsys):
    """Prevent a sync that stopped after linking from leaving history unrecorded, or recording an arrival again."""
    forge_repository(tasks, "app", ["d" * 40, "c" * 40])
    (tasks.forge.gitea / "git/repositories/alpha/app.git/hooks/pre-receive.d").mkdir()
    os.symlink(
        tasks.forge.gitea / "pre-receive-hook",
        tasks.forge.gitea / "git/repositories/alpha/app.git/hooks/pre-receive.d/porelo",
    )
    judged_project(tasks)
    assert judge(tasks).status() == 200
    assert tasks.host.arm_pushes("alpha") == ["app"]
    assert [(item.get("commit"), item["verdict"]) for item in arrivals(tasks)] == [
        ("c" * 40, "accepted"),
        ("d" * 40, "migrated"),
        (None, "armed"),
    ]


def wrong_link(repository, relative):
    """Put a link at relative inside repository, keeping what was there under the link's target."""
    path = repository if relative == "." else repository / relative
    if relative.endswith("porelo"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.symlink_to("/bin/true")
        return repository
    path.mkdir(exist_ok=True)
    moved = path.with_name(path.name + ".real")
    path.rename(moved)
    path.symlink_to(moved)
    return repository


@pytest.mark.parametrize(
    "broken",
    [
        lambda tasks: forge_repository(tasks, "app", None),
        lambda tasks: forge_repository(tasks, "app", ["d" * 40], hook=False),
        lambda tasks: forge_repository(tasks, "App", ["d" * 40]),
        lambda tasks: forge_repository(tasks, "app", ["not a commit"]),
        lambda tasks: (forge_repository(tasks, "app", ["d" * 40]), setattr(tasks.forge, "no_hook", True)),
        lambda tasks: wrong_link(forge_repository(tasks, "app", ["d" * 40]), "hooks/pre-receive.d/porelo"),
        lambda tasks: wrong_link(forge_repository(tasks, "app", ["d" * 40]), "hooks/pre-receive.d"),
        lambda tasks: wrong_link(forge_repository(tasks, "app", ["d" * 40]), "hooks"),
        lambda tasks: wrong_link(forge_repository(tasks, "app", ["d" * 40]).parent, "."),
        lambda tasks: shutil.rmtree(forge_repository(tasks, "app", ["d" * 40]).parents[1]),
    ],
    ids=[
        "history unreadable",
        "no forge hook",
        "upper case",
        "bad history",
        "judge's hook not mounted",
        "link elsewhere",
        "linked hook directory",
        "linked hooks",
        "linked organization",
        "no repositories",
    ],
)
def test_arming_stops_on_what_it_cannot_read_and_records_nothing(tasks, capsys, broken):
    """Prevent a repository armed with its history unrecorded, or armed where Forgejo's own hook is missing."""
    broken(tasks)
    with pytest.raises(tasks.scope["Refusal"]) as refused:
        tasks.host.arm_pushes("alpha")
    assert refused.value.code == 69
    assert arrivals(tasks) == [] and arrivals(tasks, "App") == []


def test_a_projects_person_reads_its_arrivals_and_no_one_else(tasks, capsys):
    """Prevent the verdicts of one project from being read by a person of another."""
    forge_repository(tasks, "app", ["d" * 40])
    tasks.host.arm_pushes("alpha")
    assert tasks.call("arrivals", "alpha", "app") == 0
    assert json.loads(capsys.readouterr().out.splitlines()[0])["commit"] == "d" * 40
    write(tasks.root, "/etc/porelo-host/people/bob.conf", record(member="beta developer"))
    assert tasks.call("arrivals", "alpha", "app", caller="bob") == 65
    assert capsys.readouterr().out == ""


def test_a_hand_admitted_person_reads_no_project_named_hand(tasks, capsys):
    """Prevent the hand admission's marker from passing for membership of a project spelt like it."""
    write(tasks.root, "/etc/porelo-host/people/bob.conf", record(member="hand"))
    assert tasks.call("arrivals", "hand", "app", caller="bob") == 65
    capsys.readouterr()


def test_reading_arrivals_of_an_unknown_project_makes_no_directory(tasks, capsys):
    """Prevent a reader from leaving directories behind for projects that have none."""
    assert tasks.call("arrivals", "alpha", "app") == 0
    assert capsys.readouterr().out == ""
    assert not (tasks.root / "var/lib/porelo-host/arrivals/alpha").exists()


def test_reading_arrivals_waits_for_a_writer_holding_the_hosts_lock(tasks, capsys):
    """Prevent a reader from seeing a lock, a removal or a sync half done."""
    import fcntl
    import threading

    forge_repository(tasks, "app", ["d" * 40])
    tasks.host.arm_pushes("alpha")
    done = []
    with (tasks.root / "etc/porelo-host/forge.conf").open("rb") as mutex:
        fcntl.flock(mutex, fcntl.LOCK_EX)
        reader = threading.Thread(target=lambda: done.append(tasks.call("arrivals", "alpha", "app", caller=None)))
        reader.start()
        reader.join(0.5)
        assert done == [], "the reader did not wait for the lock"
    reader.join(10)
    assert done == [0]
    capsys.readouterr()
