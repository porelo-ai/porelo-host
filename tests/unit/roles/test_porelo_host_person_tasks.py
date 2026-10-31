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

    def secret(self):
        value = hashlib.sha1(f"fixture-token-{self.next}".encode()).hexdigest()
        self.next += 1
        return value

    def named(self, user):
        return sorted(item["name"] for item in self.tokens.get(user, {}).values())

    def secrets(self):
        return [item["secret"] for tokens in self.tokens.values() for item in tokens.values()]

    def run(self, args, input=None):
        self.calls.append(args)
        if args[:3] == ["env", "TZ=UTC", "ssh-keygen"]:
            return self.scope["run_command"](args)
        if args[:1] == ["systemd-run"]:
            return self.check_certificate(args, input)
        assert args[:2] == ["runuser", "-u"] and args[2] == "porelo-forge", args
        offset = args.index("podman")
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

    return SimpleNamespace(host=host, forge=forge, keys=keys, call=call, root=root, applied=applied, scope=scope)


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
    ],
)
def test_a_task_names_exactly_one_principal_by_its_project(tasks, capsys, principals, code):
    """Prevent a certificate naming no project, two projects or another task from starting this task."""
    certificate = tasks.keys.certify("alice", "task", principals, TODAY, key_id="porelo task t1 by alice")
    assert tasks.call("task", "t1", data=certificate.encode()) == code
    capsys.readouterr()
    assert (records(tasks) / "t1.json").exists() == (code == 0)


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


def test_registry_revocation_drops_all_tokens_and_retries_a_failed_person(tasks, capsys):
    """Prevent an applied registry from leaving tokens live when its first deletion fails."""
    assert tasks.call("forge-token") == 0
    assert tasks.call("task", "t1", data=task_certificate(tasks).encode()) == 0
    capsys.readouterr()
    revoke(tasks)
    tasks.forge.api_failure = "alice"
    with pytest.raises(tasks.scope["Refusal"]):
        tasks.host.drop_revoked_tokens(["alice"], tasks.host.records())
    assert tasks.forge.named("porelo-alice") == []
    assert len(tasks.forge.named("alice")) == 1
    tasks.forge.api_failure = None
    tasks.host.drop_revoked_tokens(["alice"], tasks.host.records())
    assert tasks.forge.named("alice") == []
    assert tasks.forge.named(ADMIN) == []


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


@pytest.mark.parametrize("change", ["missing", "a link", "writable by others"])
def test_a_missing_krl_refuses_the_task_before_porelo_runs(tasks, capsys, change):
    """Prevent a certificate judged without the revocations in force, or against a KRL root does not hold alone."""
    krl = tasks.root / "etc/ssh/porelo-revoked.krl"
    if change == "missing":
        krl.unlink()
    elif change == "a link":
        krl.rename(krl.with_name("elsewhere.krl"))
        krl.symlink_to("elsewhere.krl")
    else:
        krl.chmod(0o666)
    assert tasks.call("task", "t1", data=task_certificate(tasks).encode()) == 73
    capsys.readouterr()
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


def test_no_porelo_on_the_host_refuses_the_task_as_unprepared(tasks, capsys):
    """Prevent root from running a porelo or systemd-run it has not checked as root's alone."""
    tasks.host.commands.discard("porelo")
    assert tasks.call("task", "t1", data=task_certificate(tasks).encode()) == 69
    capsys.readouterr()
    assert tasks.forge.checks == [] and not (records(tasks) / "t1.json").exists()
