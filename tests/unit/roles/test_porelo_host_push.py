"""Exercise the gathered sudo push, person-run migration and root check against local repositories."""

import base64
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "roles/forge/files/porelo-host-push"
ADMIN_TOKEN = "admin-token-4f1c9e"
PERSON_TOKEN = "person-token-9a3e1d"
CENTRAL_TOKEN = "central-token-7b2d5a"
FORGE_NAME = "alpha.localhost"
LOCAL_BASE = "http://127.0.0.1:3001"
CENTRAL_BASE = "https://central.example"
ELSEWHERE_BASE = "https://elsewhere.example"
GIT = shutil.which("git")
REAL_STAT = shutil.which("stat")
IDENTITY = {
    "GIT_AUTHOR_NAME": "Fixture",
    "GIT_AUTHOR_EMAIL": "fixture@example.org",
    "GIT_COMMITTER_NAME": "Fixture",
    "GIT_COMMITTER_EMAIL": "fixture@example.org",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_NOSYSTEM": "1",
}


def git(*args, cwd=None):
    result = subprocess.run(
        [GIT, *args], cwd=cwd, env={**os.environ, **IDENTITY}, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, f"fixture git {args} failed: {result.stderr}"
    return result.stdout.strip()


def commit(repository, work, name):
    """Commits the file `name` on main of the bare `repository` and returns the commit's id."""
    shutil.rmtree(work, ignore_errors=True)
    if git("--git-dir", str(repository), "for-each-ref", "refs/heads/main"):
        git("clone", "--quiet", "--branch", "main", str(repository), str(work))
    else:
        git("init", "--quiet", "--initial-branch=main", str(work))
        git("remote", "add", "origin", str(repository), cwd=work)
    (work / name).write_text(name + "\n")
    git("add", name, cwd=work)
    git("commit", "--quiet", "-m", f"Add {name}", cwd=work)
    git("push", "--quiet", "origin", "main", cwd=work)
    return git("rev-parse", "HEAD", cwd=work)


def bare(path, source=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if source is None:
        git("init", "--quiet", "--bare", "--initial-branch=main", str(path))
    else:
        git("clone", "--quiet", "--bare", str(source), str(path))
    return path


def moved_if_present(script, fixed, replacement):
    count = script.count(fixed)
    assert count <= 1, f"the command names {fixed!r} {count} times"
    return script.replace(fixed, replacement) if count == 1 else script


@pytest.fixture
def host(tmp_path):
    """A host with both forges as local repositories, the command's paths moved into the fixture.

    The command starts again with an empty environment, so each stub has its paths written into it.
    """
    person_uid = os.getuid() if os.getuid() != 0 else 1000
    etc = tmp_path / "etc"
    forge_etc = etc / "forge"
    forge_etc.mkdir(parents=True, mode=0o755)
    for ca in (forge_etc / "ca.pem", forge_etc / "central-ca.pem", etc / "system-ca.pem"):
        ca.write_text("")
        ca.chmod(0o644)
    (etc / "forge.conf").write_text(
        f"host=alpha\nname={FORGE_NAME}\n" "git_port=3001\nport=3000\naccount=porelo-forge\n"
    )
    (etc / "forge.conf").chmod(0o644)

    forge_home = tmp_path / "forge-home"
    (forge_home / ".config" / "porelo-forge").mkdir(parents=True, mode=0o700)
    api_token = forge_home / ".config" / "porelo-forge" / "api.token"
    api_token.write_text(ADMIN_TOKEN + "\n")
    api_token.chmod(0o600)

    alice_home = tmp_path / "home" / "alice"
    alice_push = alice_home / ".config" / "porelo-host" / "push"
    alice_push.mkdir(parents=True, mode=0o700)
    for parent in (alice_home, alice_home / ".config", alice_home / ".config" / "porelo-host"):
        parent.chmod(0o750)

    bob_home = tmp_path / "home" / "bob"
    bob_push = bob_home / ".config" / "porelo-host" / "push"
    bob_push.mkdir(parents=True, mode=0o700)

    decoy_home = tmp_path / "decoy-home"
    (decoy_home / ".config" / "porelo-host" / "push").mkdir(parents=True, mode=0o700)
    decoy_conf = decoy_home / ".config" / "porelo-host" / "push" / "porelo.conf"
    decoy_conf.write_text(
        f"local {ELSEWHERE_BASE}\nowner porelo\ncentral-ca {forge_etc / 'central-ca.pem'}\n"
        f"repository stand-in {ELSEWHERE_BASE}/stand-in.git\n"
    )
    decoy_conf.chmod(0o600)

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    temporary = tmp_path / "temporary"
    temporary.mkdir()
    calls = tmp_path / "calls"

    script = SCRIPT.read_text()
    script = moved_if_present(script, "/etc/porelo-host/forge/push.conf", str(forge_etc / "push.conf"))
    script = moved_if_present(script, "/home/porelo-forge/.config/porelo-forge/api.token", str(api_token))
    script = moved_if_present(script, "/etc/porelo-host/forge.conf", str(etc / "forge.conf"))
    script = moved_if_present(script, "/etc/porelo-host/forge/ca.pem", str(forge_etc / "ca.pem"))
    script = moved_if_present(script, "/etc/porelo-host/forge/central-ca.conf", str(forge_etc / "central-ca.conf"))
    script = moved_if_present(script, "/etc/ssl/certs/ca-certificates.crt", str(etc / "system-ca.pem"))
    script = moved_if_present(script, "PATH=/usr/sbin:/usr/bin", f"PATH={bin_dir}:/usr/sbin:/usr/bin")
    script = moved_if_present(script, "work=$(mktemp -d)", f"work=$(mktemp -d -p {temporary})")
    script = moved_if_present(script, "/etc/porelo-host/people", str(etc / "people"))
    script = moved_if_present(script, "/usr/local/sbin/porelo-host-person", str(bin_dir / "porelo-host-person"))
    script = moved_if_present(script, "ca_owner=0", f"ca_owner={os.getuid()}")
    (etc / "people").mkdir()
    (etc / "people/alice.conf").write_text("member=porelo developer\nlocked=false\n")
    command = tmp_path / "porelo-host-push"
    command.write_text(script)
    command.chmod(0o755)

    (bin_dir / "id").write_text(f"#!/bin/sh\ncat {tmp_path / 'uid'}\n")
    (tmp_path / "uid").write_text("0\n")

    (bin_dir / "getent").write_text(
        f"#!{sys.executable}\n"
        "import sys\n"
        "db, key = sys.argv[1], sys.argv[2]\n"
        "assert db == 'passwd', db\n"
        "entries = {\n"
        f"    '{person_uid}': 'alice:x:{person_uid}:{person_uid}::{alice_home}:/bin/bash',\n"
        f"    'alice': 'alice:x:{person_uid}:{person_uid}::{alice_home}:/bin/bash',\n"
        f"    '9999': 'bob:x:9999:9999::{bob_home}:/bin/bash',\n"
        f"    'bob': 'bob:x:9999:9999::{bob_home}:/bin/bash',\n"
        f"    'porelo-forge': 'porelo-forge:x:1234:1234::{forge_home}:/usr/sbin/nologin',\n"
        "}\n"
        "if key not in entries:\n"
        "    sys.exit(2)\n"
        "print(entries[key])\n"
    )

    foreign_marker = tmp_path / "foreign-path"
    (bin_dir / "stat").write_text(
        f"#!{sys.executable}\n"
        "import os, pathlib, subprocess, sys\n"
        f"marker = pathlib.Path({str(foreign_marker)!r})\n"
        f"real = subprocess.run([{REAL_STAT!r}, *sys.argv[1:]], capture_output=True, text=True)\n"
        "out = real.stdout\n"
        "if real.returncode == 0 and marker.exists():\n"
        "    target = marker.read_text().strip()\n"
        "    if sys.argv[-1] == target:\n"
        f"        parts = out.strip().split(' ')\n"
        f"        if parts and parts[0] == str({os.getuid()}):\n"
        "            parts[0] = '9999'\n"
        "            out = ' '.join(parts) + '\\n'\n"
        "sys.stdout.write(out)\n"
        "sys.stderr.write(real.stderr)\n"
        "sys.exit(real.returncode)\n"
    )

    (bin_dir / "runuser").write_text('#!/bin/sh\nwhile [ "$1" != -- ]; do shift; done\nshift\nexec "$@"\n')

    (bin_dir / "porelo-host-person").write_text(
        f"#!{sys.executable}\n"
        "import pathlib, sys\n"
        f"assert sys.argv[1:] == ['forge-token', '--for', 'alice'], sys.argv[1:]\n"
        f"if pathlib.Path({str(tmp_path / 'person-token-failed')!r}).exists(): sys.exit(1)\n"
        f"sys.stdout.write({PERSON_TOKEN!r})\n"
    )
    (bin_dir / "sudo").write_text(
        '#!/bin/sh\n[ "$1" = -n ] || exit 1\nshift\n[ -n "$1" ] || exit 1\n'
        f"exec {bin_dir}/porelo-host-person forge-token --for alice\n"
    )
    (bin_dir / "unshare").write_text('#!/bin/sh\n[ "$1" = --net ] || exit 1\nshift\nexport TEST_NETNS=yes\nexec "$@"\n')
    (bin_dir / "ip").write_text('#!/bin/sh\n[ "$TEST_NETNS" = yes ] && [ "$*" = "link set lo up" ]\n')
    # The namespace is stubbed: refuse every real TCP bind, and exercise the wrapper without host listeners.
    (bin_dir / "python3").write_text(
        f"#!{sys.executable}\n"
        "import os, sys\n"
        "if 'class Forward' in ' '.join(sys.argv): assert os.environ.get('TEST_NETNS') == 'yes'\n"
        "if 'TEST_NETNS' not in os.environ: os.execv(sys.executable, [sys.executable, *sys.argv[1:]])\n"
        "import socketserver\n"
        "class Server:\n"
        "    def __init__(self, address, handler):\n"
        "        assert os.environ['TEST_NETNS'] == 'yes' and address == ('127.0.0.1', 3001)\n"
        "    def serve_forever(self): pass\n"
        "    def shutdown(self): pass\n"
        "    def server_close(self): pass\n"
        "socketserver.ThreadingTCPServer = Server\n"
        "code = sys.argv[sys.argv.index('-c') + 1]\n"
        "sys.argv = ['-c', *sys.argv[sys.argv.index('-c') + 2:]]\n"
        "exec(compile(code, '<namespace>', 'exec'))\n"
    )

    repos_json = tmp_path / "forge-repos.json"
    routes_json = tmp_path / "forge-routes.json"
    bodies = tmp_path / "forge-bodies"
    (bin_dir / "curl").write_text(
        f"#!{sys.executable}\n"
        "import json, pathlib, ssl, sys, urllib.error, urllib.parse, urllib.request\n"
        f"calls = pathlib.Path({str(calls)!r})\n"
        "with calls.open('a') as handle:\n"
        "    handle.write('curl|' + ' '.join(sys.argv[1:]) + '\\n')\n"
        "args = sys.argv[1:]\n"
        "out_file = ca_file = header_arg = url = data_arg = None\n"
        "method = 'GET'\n"
        "write_code = False\n"
        "i = 0\n"
        "while i < len(args):\n"
        "    arg = args[i]\n"
        "    if arg == '-o':\n"
        "        out_file = args[i + 1]; i += 2; continue\n"
        "    if arg == '--unix-socket':\n"
        "        assert args[i + 1] == '/run/porelo-forge/git.sock'\n"
        "        i += 2; continue\n"
        "    if arg == '--cacert':\n"
        "        ca_file = args[i + 1]; i += 2; continue\n"
        "    if arg == '-H':\n"
        "        header_arg = args[i + 1]; i += 2; continue\n"
        "    if arg == '-w':\n"
        "        write_code = True; i += 2; continue\n"
        "    if arg in ('--max-time', '--noproxy'):\n"
        "        i += 2; continue\n"
        "    if arg == '-X':\n"
        "        method = args[i + 1]; i += 2; continue\n"
        "    if arg == '--data':\n"
        "        data_arg = args[i + 1]; i += 2; continue\n"
        "    if arg.startswith('https://') or arg.startswith('http://'):\n"
        "        url = arg\n"
        "    i += 1\n"
        "header_line = ''\n"
        "if header_arg and header_arg.startswith('@'):\n"
        "    header_line = pathlib.Path(header_arg[1:]).read_text().strip()\n"
        "elif header_arg:\n"
        "    header_line = header_arg\n"
        f"routes = pathlib.Path({str(routes_json)!r})\n"
        "if routes.exists():\n"
        "    table = json.loads(routes.read_text())\n"
        "    status, body = 401, {}\n"
        "    if header_line == 'Authorization: token ' + table['token']:\n"
        "        status, body = table['routes'].get(method + ' ' + urllib.parse.urlsplit(url).path, [404, {}])\n"
        "    if data_arg == '@-':\n"
        f"        with pathlib.Path({str(bodies)!r}).open('a') as handle:\n"
        "            handle.write(sys.stdin.read().strip() + '\\n')\n"
        "    if out_file:\n"
        "        pathlib.Path(out_file).write_text(json.dumps(body))\n"
        "    if write_code:\n"
        "        sys.stdout.write(str(status))\n"
        "    sys.exit(0)\n"
        f"fixture = pathlib.Path({str(repos_json)!r})\n"
        "if fixture.exists():\n"
        "    data = json.loads(fixture.read_text())\n"
        "    expected_token = data.get('token', '')\n"
        "    if expected_token and header_line != f'Authorization: token {expected_token}':\n"
        "        if out_file:\n"
        "            pathlib.Path(out_file).write_text('{}')\n"
        "        if write_code:\n"
        "            sys.stdout.write('401')\n"
        "        sys.exit(0)\n"
        "    status = data.get('status', 200)\n"
        "    pages = data.get('pages', [])\n"
        "    query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)\n"
        "    page = int(query.get('page', ['1'])[0])\n"
        "    body = pages[page - 1] if 1 <= page <= len(pages) else []\n"
        "    if out_file:\n"
        "        pathlib.Path(out_file).write_text(json.dumps(body))\n"
        "    if write_code:\n"
        "        sys.stdout.write(str(status))\n"
        "    sys.exit(0)\n"
        "class NoRedirect(urllib.request.HTTPRedirectHandler):\n"
        "    def redirect_request(self, *_a):\n"
        "        return None\n"
        "ctx = ssl.create_default_context(cafile=ca_file)\n"
        "opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),\n"
        "                                    urllib.request.HTTPSHandler(context=ctx), NoRedirect())\n"
        "headers = {}\n"
        "if ':' in header_line:\n"
        "    k, v = header_line.split(':', 1)\n"
        "    headers[k.strip()] = v.strip()\n"
        "req = urllib.request.Request(url, headers=headers, method='GET')\n"
        "try:\n"
        "    with opener.open(req, timeout=30) as resp:\n"
        "        status, raw = resp.status, resp.read()\n"
        "except urllib.error.HTTPError as err:\n"
        "    status, raw = err.code, err.read()\n"
        "if out_file:\n"
        "    pathlib.Path(out_file).write_bytes(raw)\n"
        "if write_code:\n"
        "    sys.stdout.write(str(status))\n"
    )

    (bin_dir / "git").write_text(
        f"#!{sys.executable}\n"
        "import os, pathlib, re, subprocess, sys, time\n"
        f"calls = pathlib.Path({str(calls)!r})\n"
        "args = sys.argv[1:]\n"
        f"local = any(arg.startswith({LOCAL_BASE!r}) for arg in args)\n"
        "if local:\n"
        "    assert os.environ.get('TEST_NETNS') == 'yes', 'local git escaped the namespace'\n"
        "    helper = os.environ['GIT_CONFIG_VALUE_1']\n"
        "    fd = int(re.search(r'<&([0-9]+)', helper)[1])\n"
        f"    result = subprocess.run([{GIT!r}, 'credential', 'fill'], pass_fds=(fd,),\n"
        "                            input='protocol=http\\nhost=127.0.0.1:3001\\n\\n',\n"
        "                            capture_output=True, text=True)\n"
        "    assert result.returncode == 0\n"
        # The forge's admin token as the fixture's user wrote it, so a caller's own fixture token is checked too.
        f"    expected = ({PERSON_TOKEN!r}, pathlib.Path({str(api_token)!r}).read_text().strip())\n"
        "    assert any('password=' + token + '\\n' in result.stdout for token in expected)\n"
        "with calls.open('a') as handle:\n"
        "    handle.write(\n"
        "        f\"{os.environ.get('GIT_SSL_CAINFO', '')}|\"\n"
        "        f\"{os.environ.get('GIT_CONFIG_KEY_1', '')}={os.environ.get('GIT_CONFIG_VALUE_1', '')}|\"\n"
        "        f\"{' '.join(args)}\\n\"\n"
        "    )\n"
        "if 'clone' in args and "
        f"pathlib.Path({str(tmp_path / 'clone-says-header')!r}).exists():\n"
        "    sys.stderr.write(result.stdout if local else os.environ.get('GIT_CONFIG_VALUE_0', '') + '\\n')\n"
        "    sys.exit(128)\n"
        "if 'push' in args:\n"
        f"    pathlib.Path({str(tmp_path / 'pushing')!r}).touch()\n"
        f"    if pathlib.Path({str(tmp_path / 'push-waits')!r}).exists():\n"
        "        time.sleep(5)\n"
        f"    if pathlib.Path({str(tmp_path / 'push-says-header')!r}).exists():\n"
        "        sys.stderr.write(os.environ.get('GIT_CONFIG_VALUE_0', '') + '\\n')\n"
        "        sys.exit(128)\n"
        "mapped = []\n"
        "for arg in args:\n"
        f"    arg = re.sub(r'^http://127\\.0\\.0\\.1:[0-9]+/', 'file://{tmp_path / 'local'}/', arg)\n"
        f"    arg = arg.replace('{CENTRAL_BASE}/', 'file://{tmp_path / 'central'}/')\n"
        f"    arg = arg.replace('{ELSEWHERE_BASE}/', 'file://{tmp_path / 'elsewhere'}/')\n"
        "    mapped.append(arg)\n"
        f"os.execv({GIT!r}, [{GIT!r}, *mapped])\n"
    )
    for stub in (
        "id",
        "getent",
        "stat",
        "runuser",
        "porelo-host-person",
        "sudo",
        "unshare",
        "ip",
        "python3",
        "curl",
        "git",
    ):
        (bin_dir / stub).chmod(0o755)

    central = bare(tmp_path / "central" / "stand-in.git")
    commit(central, tmp_path / "seed", "README")
    local = bare(tmp_path / "local" / "porelo" / "stand-in.git", source=central)
    central_two = bare(tmp_path / "central" / "second.git")
    commit(central_two, tmp_path / "seed", "README")
    local_two = bare(tmp_path / "local" / "porelo" / "second.git", source=central_two)

    person_conf = alice_push / "porelo.conf"
    person_conf.write_text(
        "# Written by porelo.host.bring; read by porelo-host-push.\n"
        f"local {LOCAL_BASE}\n"
        "owner porelo\n"
        f"central-ca {forge_etc / 'central-ca.pem'}\n"
        f"repository stand-in {CENTRAL_BASE}/stand-in.git\n"
        f"repository second {CENTRAL_BASE}/second.git\n"
    )
    person_conf.chmod(0o600)

    bob_conf = bob_push / "porelo.conf"
    bob_conf.write_text(person_conf.read_text())
    bob_conf.chmod(0o600)

    repos_json.write_text(
        json.dumps(
            {
                "token": ADMIN_TOKEN,
                "pages": [
                    [{"name": "stand-in", "original_url": f"{CENTRAL_BASE}/stand-in.git"}],
                    [{"name": "second", "original_url": f"{CENTRAL_BASE}/second.git"}],
                    [],
                ],
            }
        )
    )

    return {
        "root": tmp_path,
        "etc": etc,
        "forge_etc": forge_etc,
        "api_token": api_token,
        "alice_home": alice_home,
        "alice_push": alice_push,
        "person_conf": person_conf,
        "bob_push": bob_push,
        "bob_conf": bob_conf,
        "decoy_home": decoy_home,
        "person_uid": person_uid,
        "foreign_marker": foreign_marker,
        "repos_json": repos_json,
        "routes_json": routes_json,
        "bodies": bodies,
        "command": command,
        "temporary": temporary,
        "calls": calls,
        "local": local,
        "local_two": local_two,
    }


@contextmanager
def argv_watched(token):
    """Samples every process's argv while the command runs, as another account on the host could read it."""
    seen = []
    done = threading.Event()

    def sample():
        while not done.is_set():
            for cmdline in Path("/proc").glob("[0-9]*/cmdline"):
                try:
                    found = cmdline.read_bytes()
                except OSError:
                    continue
                if token.encode() in found:
                    seen.append(found)

    watcher = threading.Thread(target=sample, daemon=True)
    watcher.start()
    try:
        yield seen
    finally:
        done.set()
        watcher.join(timeout=10)


def push(host, *arguments, token=CENTRAL_TOKEN, environment=None, interrupt=False, newline=True):
    if arguments and arguments[0] == "--migrate" and environment != {"TEST_ROOT_MIGRATE": "yes"}:
        (host["root"] / "uid").write_text(f"{host['person_uid']}\n")
    process = subprocess.Popen(
        [
            "/usr/bin/env",
            "-S",
            host["command"].read_text().splitlines()[0].removeprefix("#!/usr/bin/env -S "),
            str(host["command"]),
            *arguments,
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": str(host["decoy_home"]),
            "SUDO_UID": "" if arguments and arguments[0] == "--check" else str(host["person_uid"]),
            "SUDO_USER": "" if arguments and arguments[0] == "--check" else "alice",
            **(environment or {}),
        },
        text=True,
        start_new_session=True,
    )
    if not interrupt:
        output, _ = process.communicate(token + ("\n" if newline else ""), timeout=60)
        return process.returncode, output
    process.stdin.write(token + "\n")
    process.stdin.close()
    deadline = time.monotonic() + 30
    while not (host["root"] / "pushing").exists():
        assert time.monotonic() < deadline, "the push never started"
        assert process.poll() is None, f"the command ended before its push: {process.stdout.read()}"
        time.sleep(0.05)
    # As a terminal's Ctrl+C does: the whole foreground group, git's children with it.
    os.killpg(process.pid, signal.SIGINT)
    output = process.stdout.read()
    return process.wait(timeout=30), output


def head(repository, branch="main"):
    return git("--git-dir", str(repository), "rev-parse", f"refs/heads/{branch}")


def assert_no_token_anywhere(host, output, extra_tokens=()):
    calls = host["calls"].read_text() if host["calls"].exists() else ""
    for token in (ADMIN_TOKEN, PERSON_TOKEN, CENTRAL_TOKEN, *extra_tokens):
        basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        for form in (token, basic):
            assert form not in output, f"a token was printed: {output}"
            assert form not in calls, f"a token reached a command line: {calls}"


def test_a_persons_push_reads_the_sudo_callers_config_and_token_ignoring_home(host):
    """Prevents a HOME override from choosing another person's configuration or local token."""
    central = host["root"] / "central" / "stand-in.git"
    elsewhere = bare(host["root"] / "elsewhere" / "stand-in.git")
    approved = commit(host["local"], host["root"] / "work", "B")

    code, output = push(host, "porelo", "stand-in")

    assert code == 0, f"the push was refused with {code}: {output}"
    assert head(central) == approved, f"asked for central main {approved}, got {head(central)}"
    assert not git("--git-dir", str(elsewhere), "for-each-ref"), "$HOME redirected the push config"
    assert "stand-in: taken" in output, output
    assert_no_token_anywhere(host, output)
    assert list(host["temporary"].iterdir()) == [], "the temporary clone was left behind"


def test_without_repository_names_every_configured_repository_is_pushed_in_config_order(host):
    """Prevents an unnamed push from skipping configured repositories or reordering them arbitrarily."""
    central_one = host["root"] / "central" / "stand-in.git"
    central_two = host["root"] / "central" / "second.git"
    approved_one = commit(host["local"], host["root"] / "work-one", "B")
    approved_two = commit(host["local_two"], host["root"] / "work-two", "D")

    code, output = push(host, "porelo")

    assert code == 0, f"the push was refused with {code}: {output}"
    assert head(central_one) == approved_one
    assert head(central_two) == approved_two
    assert output.index("stand-in: taken") < output.index("second: taken"), output
    assert "pushed: stand-in second" in output, output
    assert_no_token_anywhere(host, output)


def test_a_moved_central_forge_refuses_keeps_both_and_brings_its_commits_back(host):
    """Prevents a push from erasing central work, and the central work from going unseen."""
    central = host["root"] / "central" / "stand-in.git"
    central_work = commit(central, host["root"] / "central-work", "A")
    local_main = commit(host["local"], host["root"] / "work", "C")

    code, output = push(host, "porelo", "stand-in", "second")

    assert code != 0, f"a push over a moved central forge was taken: {output}"
    assert head(central) == central_work, f"central main lost {central_work}, holds {head(central)}"
    assert head(host["local"]) == local_main, f"local main moved from {local_main} to {head(host['local'])}"
    assert head(host["local"], "central/main") == central_work, "central main was not brought to the local forge"
    assert "Add A" in output, f"the refusal does not name the central commit: {output}"
    assert "not pushed either: second" in output, f"the refusal does not name what was left: {output}"
    second = host["root"] / "central" / "second.git"
    assert git("--git-dir", str(second), "log", "--format=%s", "-1", "main") == "Add README", "second was pushed"
    assert_no_token_anywhere(host, output)
    assert list(host["temporary"].iterdir()) == [], "the temporary clone was left behind"


@pytest.mark.parametrize(
    "defect, expected",
    [
        ("symlink-file", "link"),
        ("foreign-owner", "9999"),
        ("mode-0644", "0644"),
        ("dir-mode-0755", "0755"),
        ("symlink-dir", "link"),
        ("missing", "porelo.conf"),
    ],
)
def test_another_persons_or_untrusted_push_config_is_refused(host, defect, expected):
    """Prevents a developer from reading or following a symlinked, foreign-owned, or non-private push config."""
    conf = host["person_conf"]
    push_dir = host["alice_push"]
    if defect == "symlink-file":
        conf.unlink()
        conf.symlink_to(host["bob_conf"])
    elif defect == "foreign-owner":
        host["foreign_marker"].write_text(str(conf) + "\n")
    elif defect == "mode-0644":
        conf.chmod(0o644)
    elif defect == "dir-mode-0755":
        push_dir.chmod(0o755)
    elif defect == "symlink-dir":
        shutil.rmtree(push_dir)
        push_dir.symlink_to(host["bob_push"])
    else:
        conf.unlink()

    code, output = push(host, "porelo", "stand-in")

    assert code == 66, f"asked for 66 on {defect}, got {code}: {output}"
    assert expected in output, f"refusal on {defect} did not report {expected!r}: {output}"
    assert "Token" not in output, f"asked for central token on {defect}: {output}"
    assert not host["calls"].exists(), f"ran external commands on {defect}"


def test_root_running_the_persons_push_is_refused(host):
    """Prevents a direct root call from choosing a person without a sudo caller."""
    (host["root"] / "uid").write_text("0\n")

    code, output = push(host, "porelo", "stand-in", environment={"SUDO_UID": "", "SUDO_USER": ""})

    assert code == 77, f"asked for 77 when run as root, got {code}: {output}"
    assert "sudo" in output, output
    assert "Token" not in output, output
    assert not host["calls"].exists(), "commands ran when root invoked the person push"


def test_a_failed_person_token_call_stops_before_git(host):
    """Prevents an unauthenticated clone when the person helper cannot issue a local token."""
    (host["root"] / "person-token-failed").touch()

    code, output = push(host, "porelo", "stand-in")

    assert code == 69, f"asked for 69 on missing vault entry, got {code}: {output}"
    assert "forge token" in output, output
    assert "Token" not in output, f"asked for central token despite missing local vault entry: {output}"
    git_calls = [
        line
        for line in (host["calls"].read_text().splitlines() if host["calls"].exists() else [])
        if not line.startswith("porelo|")
    ]
    assert not git_calls, f"git ran without the person's local token: {git_calls}"


@pytest.mark.parametrize("stage", ["clone", "push"])
def test_what_git_says_is_shown_without_any_token(host, stage):
    """Prevents either forge token from reaching the terminal when git repeats a header."""
    commit(host["local"], host["root"] / "work", "B")
    (host["root"] / f"{stage}-says-header").touch()

    code, output = push(host, "porelo", "stand-in")

    assert code != 0, f"a push that git failed at {stage} was taken: {output}"
    assert "<redacted>" in output, f"git's header was not redacted at {stage}: {output}"
    assert_no_token_anywhere(host, output)


def test_the_callers_git_settings_cannot_send_the_push_elsewhere(host):
    """Prevents the push from following a destination planted in the caller's environment or ~/.gitconfig."""
    elsewhere = bare(host["root"] / "elsewhere" / "stand-in.git")
    central = host["root"] / "central" / "stand-in.git"
    approved = commit(host["local"], host["root"] / "work", "B")
    (host["alice_home"] / ".gitconfig").write_text(f'[url "file://{elsewhere}"]\n\tpushInsteadOf = file://{central}\n')
    planted = f"'url.file://{elsewhere}.pushInsteadOf'='file://{central}'"

    code, output = push(host, "porelo", "stand-in", environment={"GIT_CONFIG_PARAMETERS": planted})

    assert code == 0, f"the push was refused with {code}: {output}"
    assert head(central) == approved, f"asked for central main {approved}, got {head(central)}"
    assert not git("--git-dir", str(elsewhere), "for-each-ref"), "the push went where the caller's git config said"


def test_each_forge_is_trusted_by_its_own_authority_and_no_redirect_is_followed(host):
    """Prevents the host's CA from vouching for the central forge, and a token sent on to a redirect's host."""
    commit(host["local"], host["root"] / "work", "B")
    forge_etc = host["forge_etc"]

    code, output = push(host, "porelo", "stand-in")

    assert code == 0, f"the push was refused with {code}: {output}"
    lines = host["calls"].read_text().splitlines()
    central = [line for line in lines if CENTRAL_BASE in line and not line.startswith("curl|")]
    assert central
    assert all(line.startswith(str(forge_etc / "central-ca.pem") + "|http.followRedirects=false|") for line in central)
    local = [line for line in lines if LOCAL_BASE in line]
    assert local and all(line.startswith("|") for line in local)


def test_unknown_or_duplicate_repositories_are_refused_before_tokens_are_asked(host):
    """Prevents a half-done push or credential prompt when repository names are unknown or repeated."""
    code, output = push(host, "porelo", "stand-in", "elsewhere")
    assert code == 64 and "elsewhere" in output and "Token" not in output, (code, output)
    assert not host["calls"].exists()

    code, output = push(host, "porelo", "stand-in", "stand-in")
    assert code == 64 and "Token" not in output, (code, output)
    assert not host["calls"].exists()


def test_an_interrupted_push_leaves_no_clone_behind_and_pushes_nothing(host):
    """Prevents a clone of private work left on the host, and a push that goes on after Ctrl+C."""
    central = host["root"] / "central" / "stand-in.git"
    before = head(central)
    commit(host["local"], host["root"] / "work", "B")
    (host["root"] / "push-waits").touch()

    code, output = push(host, "porelo", "stand-in", interrupt=True)

    assert code == 130, f"asked for 130 after an interrupt, got {code}: {output}"
    assert head(central) == before, "the push went on after the interrupt"
    assert list(host["temporary"].iterdir()) == [], "the interrupted push left its clone behind"


def test_check_reads_original_url_as_root_and_refuses_unpushed_or_missing_url(host):
    """Prevents project removal from reading push.conf, running non-root, or deleting unpushed or unmigrated work."""
    # Non-root cannot run --check.
    (host["root"] / "uid").write_text(f"{host['person_uid']}\n")
    code, output = push(host, "--check", "porelo", "stand-in")
    assert code == 77, f"asked for 77 when non-root runs --check, got {code}: {output}"

    (host["root"] / "uid").write_text("0\n")
    # Deleting the person's config and ensuring no root push.conf exists proves --check reads neither.
    host["person_conf"].unlink()
    assert not (host["forge_etc"] / "push.conf").exists()

    # Unpushed work on a branch is refused with 65.
    pending = commit(host["local"], host["root"] / "work", "pending")
    code, output = push(host, "--check", "porelo", "stand-in", "second")
    assert code == 65 and "stand-in" in output and "unpushed" in output, (code, output)
    assert_no_token_anywhere(host, output)

    # Once central holds that commit, --check exits 0 using default system CA, or central-ca.conf when present.
    central = host["root"] / "central" / "stand-in.git"
    git("--git-dir", str(host["local"]), "push", str(central), f"{pending}:refs/heads/main")
    host["calls"].unlink(missing_ok=True)
    code, output = push(host, "--check", "porelo", "stand-in", "second")
    assert code == 0, f"expected clean --check to pass, got {code}: {output}"
    fetch_cas = [
        line.split("|", 2)[0]
        for line in host["calls"].read_text().splitlines()
        if not line.startswith(("porelo|", "curl|")) and " fetch " in f" {line.split('|', 2)[2]} "
    ]
    assert fetch_cas == [str(host["etc"] / "system-ca.pem"), str(host["etc"] / "system-ca.pem")], fetch_cas
    assert_no_token_anywhere(host, output)

    custom_ca = host["forge_etc"] / "central-ca.pem"
    (host["forge_etc"] / "central-ca.conf").write_text(str(custom_ca) + "\n")
    (host["forge_etc"] / "central-ca.conf").chmod(0o644)
    host["calls"].unlink(missing_ok=True)
    code, output = push(host, "--check", "porelo", "stand-in")
    assert code == 0, (code, output)
    fetch_cas = [
        line.split("|", 2)[0]
        for line in host["calls"].read_text().splitlines()
        if not line.startswith(("porelo|", "curl|")) and " fetch " in f" {line.split('|', 2)[2]} "
    ]
    assert fetch_cas == [str(custom_ca)], fetch_cas

    # A repository without an original_url in Forgejo is refused by name.
    host["repos_json"].write_text(
        json.dumps(
            {
                "token": ADMIN_TOKEN,
                "pages": [
                    [{"name": "stand-in", "original_url": f"{CENTRAL_BASE}/stand-in.git"}],
                    [{"name": "second", "original_url": ""}],
                    [],
                ],
            }
        )
    )
    code, output = push(host, "--check", "porelo", "stand-in", "second")
    assert code == 69 and "second" in output, f"asked for 69 naming second without original_url, got {code}: {output}"
    assert_no_token_anywhere(host, output)


@pytest.mark.parametrize("token_defect", ["stdin-symlink", "unreadable"])
def test_check_admin_token_file_defects_stop_before_git(host, token_defect):
    """Prevents --check from reading stdin through a token symlink or proceeding without the admin token."""
    (host["root"] / "uid").write_text("0\n")
    if token_defect == "stdin-symlink":
        host["api_token"].unlink()
        host["api_token"].symlink_to("/dev/stdin")
    else:
        host["api_token"].chmod(0o000)

    code, output = push(host, "--check", "porelo", "stand-in")

    assert code == 66, f"asked for 66 on {token_defect}, got {code}: {output}"
    assert "api.token" in output, f"refusal did not name api.token on {token_defect}: {output}"
    assert not host["calls"].exists(), f"commands ran despite {token_defect}"


def test_nothing_reads_or_writes_roots_push_conf():
    """Prevents reintroducing root's shared push.conf or omitting porelo-host-push installation from up."""
    searched = [*sorted((ROOT / "roles").rglob("*")), *sorted((ROOT / "playbooks").rglob("*"))]
    files = [path for path in searched if path.is_file() and path.suffix != ".md"]
    known = [path for path in files if "/usr/local/sbin/porelo-host-push" in path.read_text(encoding="utf-8")]
    assert known, "verified search scope did not match /usr/local/sbin/porelo-host-push"
    offenders = [path for path in files if "push.conf" in path.read_text(encoding="utf-8")]
    assert not offenders, f"root's push.conf is still named in: {offenders}"
    main_tasks = (ROOT / "roles/forge/tasks/main.yml").read_text(encoding="utf-8")
    assert "tasks/push.yml" in main_tasks, "roles/forge/tasks/main.yml does not include tasks/push.yml"


def migration(host, routes):
    """The bring's list of repositories still to migrate, and a forge that answers the person's own token."""
    listed = host["alice_push"] / "porelo.migrate"
    listed.write_text(
        "# Written by porelo.host.bring; read by porelo-host-push --migrate.\n"
        f"local {LOCAL_BASE}\n"
        "owner porelo\n"
        f"central-ca {host['forge_etc'] / 'central-ca.pem'}\n"
        f"repository stand-in {CENTRAL_BASE}/stand-in.git\n"
        f"repository second {CENTRAL_BASE}/second.git\n"
    )
    listed.chmod(0o600)
    host["routes_json"].write_text(json.dumps({"token": PERSON_TOKEN, "routes": routes}))
    return listed


def test_migrate_takes_only_the_missing_repositories_with_the_central_token_in_the_body_alone(host):
    """Prevents the central token from lying on the host, or reaching an argv, a log or an answer, at migration."""
    listed = migration(
        host,
        {
            "GET /api/v1/repos/porelo/stand-in": [200, {"name": "stand-in"}],
            "GET /api/v1/repos/porelo/second": [404, {}],
            "POST /api/v1/repos/migrate": [201, {"name": "second"}],
        },
    )

    with argv_watched(CENTRAL_TOKEN) as seen:
        code, output = push(host, "--migrate", "porelo", newline=False)

    assert code == 0, output
    assert "stand-in: already on the forge" in output and "second: migrated" in output, output
    bodies = [json.loads(line) for line in host["bodies"].read_text().splitlines()]
    assert bodies == [
        {
            "clone_addr": f"{CENTRAL_BASE}/second.git",
            "repo_name": "second",
            "repo_owner": "porelo",
            "service": "git",
            "mirror": False,
            "private": True,
            "auth_token": CENTRAL_TOKEN,
        }
    ]
    assert not seen, f"the central token was in an argv: {seen}"
    assert_no_token_anywhere(host, output)
    assert not listed.exists(), "the migration list outlived a migration that took every repository"
    files = [path for path in host["root"].rglob("*") if path.is_file() and path != host["bodies"]]
    assert not [path for path in files if CENTRAL_TOKEN.encode() in path.read_bytes()], "the token lies in a file"
    assert list(host["temporary"].iterdir()) == [], "the temporary answer was left behind"


def test_a_migration_the_forge_refuses_names_its_answer_and_keeps_the_list(host):
    """Prevents a refused migration from passing silently or losing what is still to migrate."""
    listed = migration(
        host,
        {
            "GET /api/v1/repos/porelo/stand-in": [404, {}],
            "GET /api/v1/repos/porelo/second": [404, {}],
            "POST /api/v1/repos/migrate": [422, {"message": "clone address refused"}],
        },
    )

    code, output = push(host, "--migrate", "porelo")

    assert code == 65, output
    assert "stand-in: the forge answered HTTP 422: clone address refused" in output, output
    assert listed.exists(), "the migration list went although nothing was migrated"
    assert_no_token_anywhere(host, output)


def test_migrate_runs_only_in_the_persons_own_account_from_their_own_list(host):
    """Prevents root, or a list another account could write, from deciding what is migrated with the token."""
    migration(host, {})
    host["root"].joinpath("uid").write_text("0\n")
    code, output = push(host, "--migrate", "porelo", environment={"TEST_ROOT_MIGRATE": "yes"})
    assert code == 77, output

    host["root"].joinpath("uid").write_text(f"{host['person_uid']}\n")
    (host["alice_push"] / "porelo.migrate").chmod(0o644)
    code, output = push(host, "--migrate", "porelo")
    assert code == 66 and "porelo.migrate" in output, output

    (host["alice_push"] / "porelo.migrate").chmod(0o600)
    host["foreign_marker"].write_text(str(host["alice_push"] / "porelo.migrate"))
    code, output = push(host, "--migrate", "porelo")
    assert code == 66 and "9999" in output, output
    host["foreign_marker"].unlink()

    elsewhere = host["root"] / "elsewhere.migrate"
    (host["alice_push"] / "porelo.migrate").rename(elsewhere)
    (host["alice_push"] / "porelo.migrate").symlink_to(elsewhere)
    code, output = push(host, "--migrate", "porelo")
    assert code == 66 and "link" in output, output
    assert not host["bodies"].exists(), "a request body was sent"


def test_pull_brings_central_main_to_the_local_forge_as_central_main(host):
    """Prevents the central state from reaching the host only through a token kept there."""
    central = host["root"] / "central" / "stand-in.git"
    local_main = head(host["local"])
    central_work = commit(central, host["root"] / "central-work", "A")

    with argv_watched(CENTRAL_TOKEN) as seen:
        code, output = push(host, "--pull", "porelo", "stand-in")

    assert code == 0, output
    assert head(host["local"], "central/main") == central_work, "central main did not reach the local forge"
    assert head(host["local"]) == local_main, "local main was moved past its protection"
    assert "stand-in: central main is 1 commit ahead" in output, output
    assert not seen, f"the central token was in an argv: {seen}"
    assert_no_token_anywhere(host, output)
    assert list(host["temporary"].iterdir()) == [], "the temporary clone was left behind"


def test_pull_says_when_local_main_is_central_main(host):
    """Prevents an empty branch from being brought where nothing is to merge."""
    code, output = push(host, "--pull", "porelo", "stand-in")

    assert code == 0, output
    assert "stand-in: local main is central main" in output, output
    assert not git("--git-dir", str(host["local"]), "for-each-ref", "refs/heads/central/main")


def test_pull_says_when_local_main_is_ahead_and_brings_nothing(host):
    """Prevents an older central main from being brought back as if the two had gone apart."""
    commit(host["local"], host["root"] / "work", "C")

    code, output = push(host, "--pull", "porelo", "stand-in")

    assert code == 0, output
    assert "stand-in: local main is ahead of central main" in output, output
    assert not git("--git-dir", str(host["local"]), "for-each-ref", "refs/heads/central/main")


@pytest.mark.parametrize(
    "environment",
    [
        {"SUDO_UID": "0"},
        {"SUDO_UID": "9999"},
        {"SUDO_USER": "bob"},
        {"SUDO_UID": "invalid"},
        {"SUDO_USER": "../alice"},
    ],
)
def test_false_sudo_callers_are_refused_before_credentials(host, environment):
    """Prevent root rights from being used with a forged or inconsistent caller identity."""
    code, output = push(host, "porelo", environment=environment)
    assert code == 77 and "Token" not in output
    assert not host["calls"].exists()


def test_a_removed_developer_cannot_use_an_old_push_config(host):
    """Prevent a former member from sending work with a stale configuration."""
    (host["etc"] / "people/alice.conf").write_text("member=other developer\nlocked=false\n")
    code, output = push(host, "porelo")
    assert code == 77 and "Token" not in output
    assert not host["calls"].exists()


def test_socket_api_and_sudoers_contract(host):
    """Prevent local API traffic escaping to TCP and sudo granting unrelated root verbs."""
    code, output = push(host, "--check", "porelo", "stand-in")
    assert code == 0, output
    calls = host["calls"].read_text().splitlines()
    api = [line for line in calls if line.startswith("curl|")]
    assert api and all("--unix-socket /run/porelo-forge/git.sock" in line for line in api)
    assert all("http://localhost/api/v1/" in line and "--cacert" not in line for line in api)
    rules = (ROOT / "roles/forge/files/porelo-host-push.sudoers").read_text().splitlines()
    assert [line for line in rules if line and not line.startswith("#")] == [
        "%porelo-people ALL=(root) NOPASSWD: /usr/local/sbin/porelo-host-push *"
    ]
    tasks = yaml.safe_load((ROOT / "roles/forge/tasks/push.yml").read_text())
    installed = [task["ansible.builtin.copy"] for task in tasks if "ansible.builtin.copy" in task]
    rule = next(task for task in installed if task["dest"] == "/etc/sudoers.d/porelo-host-push")
    assert rule["owner"] == rule["group"] == "root" and rule["mode"] == "0440"
    assert rule["validate"] == "/usr/sbin/visudo -cf %s"
    assert rule["src"] == "{{ role_path }}/files/porelo-host-push.sudoers"
    down = yaml.safe_load((ROOT / "roles/forge/tasks/down.yml").read_text())
    assert any("/etc/sudoers.d/porelo-host-push" in task.get("loop", []) for task in down)


@pytest.mark.parametrize("stage", ["unshare", "ip"])
def test_namespace_setup_failure_never_falls_back_to_host_git(host, stage):
    """Prevent a failed namespace or loopback setup from opening a host listener or sending work."""
    stub = host["root"] / "bin" / stage
    stub.write_text("#!/bin/sh\nexit 1\n")
    before = head(host["root"] / "central/stand-in.git")
    code, output = push(host, "--pull", "porelo", "stand-in")
    assert code != 0
    calls = host["calls"].read_text() if host["calls"].exists() else ""
    assert LOCAL_BASE not in calls
    assert head(host["root"] / "central/stand-in.git") == before
    assert_no_token_anywhere(host, output)
    assert list(host["temporary"].iterdir()) == []


@pytest.mark.parametrize("entry", ["", "local http://127.0.0.1:9999"])
def test_missing_or_foreign_local_destination_is_refused_before_credentials(host, entry):
    """Prevent a user-controlled config from directing root's Git to another destination."""
    conf = host["person_conf"]
    conf.write_text(conf.read_text().replace(f"local {LOCAL_BASE}", entry))
    code, output = push(host, "porelo")
    assert code == 65 and "Token" not in output
    assert not host["calls"].exists()


def test_a_config_swapped_after_ownership_checks_is_not_read_with_root_rights(host):
    """Prevent a caller from racing the config check to expose a root-only file in diagnostics."""
    conf = host["person_conf"]
    protected = host["root"] / "protected"
    protected.write_text("private-fixture-content\n")
    stat_stub = host["root"] / "bin/stat"
    stat_stub.write_text(stat_stub.read_text().replace("sys.exit(real.returncode)\n", ""))
    with stat_stub.open("a") as stream:
        stream.write(f"if sys.argv[-1] == {str(conf)!r}:\n")
        stream.write(f"    pathlib.Path({str(conf)!r}).unlink()\n")
        stream.write(f"    pathlib.Path({str(conf)!r}).symlink_to({str(protected)!r})\n")
    runuser = host["root"] / "bin/runuser"
    runuser.write_text(
        '#!/bin/sh\nwhile [ "$1" != -- ]; do shift; done\nshift\n'
        f'[ "$1" != cat ] || [ "$3" != "{conf}" ] || exit 1\n'
        'exec "$@"\n'
    )
    code, output = push(host, "porelo")
    assert code == 66
    assert "private-fixture-content" not in output
    assert not host["calls"].exists()


@pytest.mark.parametrize("environment", [{"SUDO_UID": "1000"}, {"SUDO_USER": "alice"}, {"SUDO_UID": "0"}])
def test_check_refuses_sudo_even_when_effective_uid_is_root(host, environment):
    """Prevent sudoers callers from bypassing membership checks to read private repositories."""
    code, output = push(host, "--check", "porelo", "stand-in", environment=environment)
    assert code == 77 and "Token" not in output, (code, output)
    assert not host["calls"].exists()


@pytest.mark.parametrize("mode", ["push", "migrate"])
def test_token_helpers_cannot_consume_the_central_credential(host, mode):
    """Prevent a helper or sudo relay from consuming or observing the central token on stdin."""
    helper = host["root"] / "bin/porelo-host-person"
    helper.write_text(
        helper.read_text().replace(
            "import pathlib, sys\n", "import pathlib, sys\n" "assert sys.stdin.buffer.read() == b''\n"
        )
    )
    arguments = ("porelo", "stand-in")
    if mode == "migrate":
        migration(host, {"GET /api/v1/repos/porelo/stand-in": [200, {}], "GET /api/v1/repos/porelo/second": [200, {}]})
        arguments = ("--migrate", "porelo")
    code, output = push(host, *arguments)
    assert code == 0, (code, output)
    assert_no_token_anywhere(host, output)


def test_oversized_config_is_refused_before_credentials(host):
    """Prevent root from buffering an arbitrarily large caller-controlled config."""
    with host["person_conf"].open("a") as stream:
        stream.write("#" + "x" * 131072 + "\n")
    code, output = push(host, "porelo")
    assert code == 66 and "Token" not in output, (code, output)
    assert not host["calls"].exists()


def test_config_swapped_to_a_device_is_refused_after_reading(host):
    """Prevent a path swapped after stat from passing as a regular config file."""
    conf = host["person_conf"]
    runuser = host["root"] / "bin/runuser"
    runuser.write_text(
        '#!/bin/sh\nwhile [ "$1" != -- ]; do shift; done\nshift\n'
        f'rm -- "{conf}"\nln -s /dev/null "{conf}"\nexec "$@"\n'
    )
    code, output = push(host, "porelo")
    assert code == 66 and "plain file" in output, (code, output)
    assert not host["calls"].exists()


def namespace_source():
    return SCRIPT.read_text().split("unshare --net python3 -I -c '\n", 1)[1].split('\n\' "$git_port"', 1)[0]


@pytest.mark.parametrize("failure", ["send", "recv", "shutdown", "idle"])
def test_forwarder_drains_early_gate_answers_and_closes_sockets(failure):
    """Prevent early HTTP refusals from being dropped and socket failures from printing tracebacks or hanging."""
    import ast
    import selectors
    import socket
    import socketserver
    from types import SimpleNamespace

    class Endpoint:
        def __init__(self, packets):
            self.packets = iter(packets)
            self.sent = b""
            self.closed = False
            self.timeout = None

        def __enter__(self):
            return self

        def __exit__(self, *_):
            self.close()

        def connect(self, _):
            pass

        def settimeout(self, value):
            self.timeout = value

        def recv(self, _):
            if failure == "recv" and self is request:
                raise ConnectionResetError()
            return next(self.packets, b"")

        def sendall(self, data):
            if failure == "send" and self is peer:
                raise BrokenPipeError()
            self.sent += data

        def shutdown(self, _):
            if failure == "shutdown":
                raise OSError("not connected")

        def close(self):
            self.closed = True

    answer = b"HTTP/1.1 401 Unauthorized\r\nConnection: close\r\n\r\nrefused"
    request = Endpoint([b"unfinished request", b""])
    peer = Endpoint([answer, b""])

    class Ready:
        def __init__(self):
            self.keys = {}

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def register(self, source, events, target):
            self.keys[source] = SimpleNamespace(fileobj=source, data=target)

        def unregister(self, source):
            del self.keys[source]

        def get_map(self):
            return self.keys

        def select(self, timeout=None):
            if failure == "idle":
                assert timeout and timeout <= 30, "an idle forwarder must have a finite deadline"
                return []
            return [(key, selectors.EVENT_READ) for key in list(self.keys.values())]

    tree = ast.parse(namespace_source())
    forward = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Forward")
    scope = {
        "socketserver": socketserver,
        "selectors": SimpleNamespace(DefaultSelector=Ready, EVENT_READ=selectors.EVENT_READ),
        "socket": SimpleNamespace(
            socket=lambda *_: peer, AF_UNIX=socket.AF_UNIX, SOCK_STREAM=socket.SOCK_STREAM, SHUT_WR=socket.SHUT_WR
        ),
        "upstream": "unused",
    }
    exec(compile(ast.Module(body=[forward], type_ignores=[]), "<forwarder>", "exec"), scope)
    scope["Forward"](request, None, None)
    if failure != "idle":
        assert request.sent == answer, "the gate's refusal must still reach git"
    assert request.closed and peer.closed, "both ends must close after EOF, failure or timeout"
    assert request.timeout and peer.timeout, "send and recv must have finite timeouts"


@pytest.mark.parametrize("transfer", ["local", "central"])
@pytest.mark.parametrize("signum", [signal.SIGTERM, signal.SIGINT, signal.SIGHUP])
def test_signalling_only_the_helper_stops_namespace_git_and_removes_work(host, signum, transfer):
    """Prevent orphaned git descendants and private clones after the helper alone receives a signal."""
    marker = host["root"] / "namespace-processes"
    git_stub = host["root"] / "bin/git"
    original_git = host["root"] / "bin/original-git"
    git_stub.rename(original_git)
    git_stub.write_text(
        f"#!{sys.executable}\n"
        "import os, pathlib, signal, subprocess, sys, time\n"
        f"if {transfer!r} == 'central' and not any(arg.startswith({CENTRAL_BASE!r}) for arg in sys.argv):\n"
        f"    os.execv({str(original_git)!r}, [{str(original_git)!r}, *sys.argv[1:]])\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        f"pathlib.Path({str(marker)!r}).write_text(str(os.getpid()) + ' ' + str(child.pid))\n"
        "time.sleep(60)\n"
    )
    git_stub.chmod(0o755)
    process = subprocess.Popen(
        [str(host["command"]), "porelo", "stand-in"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
        env={"SUDO_UID": str(host["person_uid"]), "SUDO_USER": "alice"},
    )
    pids = []
    try:
        process.stdin.write(CENTRAL_TOKEN + "\n")
        process.stdin.flush()
        deadline = time.monotonic() + 10
        while not marker.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        assert marker.exists(), f"{transfer} git never started"
        pids = [int(pid) for pid in marker.read_text().split()]
        if transfer == "local":
            parent_pid = int(Path(f"/proc/{pids[0]}/stat").read_text().split()[3])
            assert os.getpgid(pids[0]) == os.getpgid(parent_pid), "Git escaped the forwarder process group"
        process.send_signal(signum)
        try:
            output, _ = process.communicate(timeout=8)
        except subprocess.TimeoutExpired:
            pytest.fail("the helper did not stop its namespace after a signal")
        assert process.returncode == 128 + signum, (process.returncode, output)
        assert list(host["temporary"].iterdir()) == [], "the private clone directory survived the signal"
        for pid in pids:
            status = Path(f"/proc/{pid}/stat")
            assert not status.exists() or status.read_text().split()[2] == "Z", f"git descendant {pid} is still running"
        assert "Traceback" not in output
    finally:
        for pid in pids:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
        process.communicate(timeout=5)


def test_large_local_credentials_reach_the_namespace_on_a_pipe(host):
    """Prevent Bash from spilling a large credential to a here-string temporary file."""
    large_token = "fixture-" + "x" * 65536
    helper = host["root"] / "bin/porelo-host-person"
    helper.write_text(helper.read_text().replace(repr(PERSON_TOKEN), repr(large_token)))
    marker = host["root"] / "credential-is-pipe"
    python_stub = host["root"] / "bin/python3"
    python_stub.write_text(
        python_stub.read_text().replace(
            "import socketserver\n",
            "import pathlib, socketserver, stat\n"
            f"pathlib.Path({str(marker)!r}).write_text(str(stat.S_ISFIFO(os.fstat(0).st_mode)))\n"
            "sys.exit(1)\n",
        )
    )
    code, output = push(host, "porelo", "stand-in")
    assert code != 0, "the namespace test stub must refuse before starting Git"
    assert marker.read_text() == "True", "the local credential reached a disk-backed stdin"
    assert large_token not in output
    assert list(host["temporary"].iterdir()) == []


@pytest.mark.parametrize("padding", [b"\n", b"\0"])
def test_raw_config_limit_cannot_be_hidden_by_shell_substitution(host, padding):
    """Prevent truncation of an oversized config from silently omitting repositories."""
    conf = host["person_conf"]
    content = conf.read_bytes()
    conf.write_bytes(content + padding * (65537 - len(content)))
    code, output = push(host, "porelo", "stand-in")
    assert code == 66 and "64 KiB" in output, (code, output)
    assert not host["calls"].exists(), "an oversized config reached the forge"


def test_nul_in_config_is_refused_before_credentials(host):
    """Prevent shell NUL removal from changing the configuration's meaning."""
    with host["person_conf"].open("ab") as stream:
        stream.write(b"# invisible\0suffix\n")
    code, output = push(host, "porelo", "stand-in")
    assert code == 66 and "NUL" in output, (code, output)
    assert not host["calls"].exists()


def capture_source():
    return SCRIPT.read_text().split("capture_git() {\n", 1)[1].split("\n}\n", 1)[0]


def run_capture(setup, command):
    return subprocess.run(
        [
            "bash",
            "--noprofile",
            "--norc",
            "-c",
            "set -euo pipefail\nactive_pid=\n" + setup + "\ncapture_git() {\n" + capture_source() + "\n}\n" + command,
        ],
        capture_output=True,
        timeout=10,
    )


def test_early_coproc_exit_diagnoses_a_broken_credential_pipe():
    """Prevent an early namespace failure from killing the parent shell with SIGPIPE."""
    result = run_capture(
        "local_token=$(printf '%1000000s' x)\nas_local() { return 42; }",
        'status=0; capture_git as_local || status=$?; printf "survived:%s" "$status"',
    )
    assert result.returncode == 0, (result.returncode, result.stderr)
    assert b"survived:" in result.stdout and b"survived:0" not in result.stdout
    assert b"credential" in result.stderr, result.stderr
    assert b"unbound variable" not in result.stderr


def test_reaped_coproc_keeps_its_saved_pid_and_output_descriptors():
    """Prevent a fast exit from discarding Git's refusal or aborting under nounset."""
    result = run_capture(
        "local_token=x\nas_local() { printf refusal; return 42; }\n"
        "set -T\ntrap 'case $BASH_COMMAND in active_pid=*|local\\ output_fd=*) sleep 0.1;; esac' DEBUG",
        'status=0; capture_git as_local || status=$?; printf "%s:%s" "$status" "$said"',
    )
    assert result.returncode == 0 and result.stdout == b"42:refusal", (result.returncode, result.stdout, result.stderr)
    assert b"Bad file descriptor" not in result.stderr


def test_coproc_output_is_drained_past_nul_bytes():
    """Prevent truncated diagnostics and SIGPIPE in Git when stderr contains a NUL."""
    result = run_capture(
        "producer() { printf 'before\\0'; printf '%100000s' x; printf after; }",
        'status=0; capture_git producer || status=$?; printf "%s:%s" "$status" "${said: -5}"',
    )
    assert result.returncode == 0 and result.stdout == b"0:after", (result.returncode, result.stdout, result.stderr)


def test_cleanup_uses_transfer_pid_before_active_pid_is_assigned(tmp_path):
    """Prevent a signal during coproc setup from leaving its process group alive."""
    source = SCRIPT.read_text().split("clean_up() {\n", 1)[1].split("\n}\n", 1)[0]
    result = subprocess.run(
        [
            "bash",
            "-c",
            "set -eu\nactive_pid=\nTRANSFER_PID=12345\nchecking=\n"
            f"work={str(tmp_path / 'work')!r}\n"
            "kill() { printf '%s\\n' \"$*\"; }\nsleep() { :; }\nwait() { :; }\n"
            + "clean_up() {\n"
            + source
            + "\n}\nclean_up",
        ],
        capture_output=True,
        timeout=5,
    )
    assert result.returncode == 0 and b"-TERM -- -12345" in result.stdout, (result.stdout, result.stderr)
    assert b"-KILL -- -12345" in result.stdout


@pytest.mark.parametrize("replacement", ["mode", "directory-link", "fifo"])
def test_config_read_checks_the_open_descriptor_and_ancestor_directories(host, replacement):
    """Prevent a caller racing the path checks from supplying unsafe config bytes."""
    conf = host["person_conf"]
    runuser = host["root"] / "bin/runuser"
    setup = ""
    if replacement == "mode":
        setup = f"os.chmod({str(conf)!r}, 0o644)\n"
    elif replacement == "directory-link":
        directory = host["alice_home"] / ".config"
        moved = host["alice_home"] / "moved-config"
        setup = f"os.rename({str(directory)!r}, {str(moved)!r})\nos.symlink({str(moved)!r}, {str(directory)!r})\n"
    else:
        saved = conf.with_suffix(".saved")
        writer = (
            "import errno, os, pathlib, time\n"
            f"path = {str(conf)!r}\n"
            "deadline = time.monotonic() + 2\n"
            "while time.monotonic() < deadline:\n"
            "    try:\n"
            "        fd = os.open(path, os.O_WRONLY | os.O_NONBLOCK)\n"
            "        break\n"
            "    except OSError as error:\n"
            "        if error.errno != errno.ENXIO: raise\n"
            "        time.sleep(0.01)\n"
            "else: raise SystemExit(0)\n"
            f"os.replace({str(saved)!r}, path)\n"
            "with os.fdopen(fd, 'wb') as stream: stream.write(pathlib.Path(path).read_bytes())\n"
        )
        setup = (
            f"os.rename({str(conf)!r}, {str(saved)!r})\nos.mkfifo({str(conf)!r}, 0o600)\n"
            f"subprocess.Popen([sys.executable, '-c', {writer!r}], stdin=subprocess.DEVNULL, "
            "stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
        )
    runuser.write_text(
        f"#!{sys.executable}\nimport os, subprocess, sys\n"
        + setup
        + "args = sys.argv[sys.argv.index('--') + 1:]\nos.execvp(args[0], args)\n"
    )
    code, output = push(host, "porelo", "stand-in")
    assert code == 66, (replacement, code, output)
    assert not host["calls"].exists(), "unsafe caller config reached the forge"


def test_completed_namespace_git_does_not_leave_a_helper_holding_output_open(host):
    """Prevent a Git helper ignoring TERM from hanging output capture after Git exits."""
    marker = host["root"] / "helper-group"
    git_stub = host["root"] / "bin/git"
    helper = (
        "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); print('ready', flush=True); time.sleep(60)"
    )
    git_stub.write_text(
        f"#!{sys.executable}\nimport os, pathlib, subprocess, sys\n"
        f"child = subprocess.Popen([sys.executable, '-c', {helper!r}], stdout=subprocess.PIPE)\n"
        "assert child.stdout.readline() == b'ready\\n'\n"
        # Give the helper the captured stderr too, so it can keep the transfer output open.
        f"pathlib.Path({str(marker)!r}).write_text(str(os.getpgrp()) + ' ' + str(child.pid))\n"
    )
    script = "as_local() {\n" + SCRIPT.read_text().split("as_local() {\n", 1)[1].split("\n}\n", 1)[0] + "\n}\n"
    process = subprocess.Popen(
        ["bash", "-c", "git_port=3001\nlocal_socket=unused\n" + script + "as_local version"],
        env={"PATH": f"{host['root'] / 'bin'}:/usr/bin:/bin"},
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        try:
            output, _ = process.communicate(b"fixture-token\n", timeout=5)
        except subprocess.TimeoutExpired:
            pytest.fail("a helper kept namespace output open after Git completed")
        assert process.returncode == 0, (process.returncode, output)
        assert marker.exists(), output
        helper_pid = marker.read_text().split()[1]
        status = Path(f"/proc/{helper_pid}/stat")
        assert not status.exists() or status.read_text().split()[2] == "Z", "Git's helper survived completion"
    finally:
        if marker.exists():
            group = int(marker.read_text().split()[0])
            try:
                os.killpg(group, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=5)
