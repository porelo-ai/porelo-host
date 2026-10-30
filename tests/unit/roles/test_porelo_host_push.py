"""Exercise the gathered push as an unprivileged developer and its root check against local repositories."""

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

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "roles/forge/files/porelo-host-push"
ADMIN_TOKEN = "admin-token-4f1c9e"
PERSON_TOKEN = "person-token-9a3e1d"
CENTRAL_TOKEN = "central-token-7b2d5a"
FORGE_NAME = "forge.alpha.porelo.internal"
LOCAL_BASE = "https://127.0.0.1:3000"
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
        f"address=127.0.0.1\nhost=alpha\nname={FORGE_NAME}\n"
        "matrix_name=matrix.alpha.porelo.internal\nport=3000\naccount=porelo-forge\n"
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
    vault_calls = tmp_path / "vault-calls"

    script = SCRIPT.read_text()
    script = moved_if_present(script, "/etc/porelo-host/forge/push.conf", str(forge_etc / "push.conf"))
    script = moved_if_present(script, "/home/porelo-forge/.config/porelo-forge/api.token", str(api_token))
    script = moved_if_present(script, "/etc/porelo-host/forge.conf", str(etc / "forge.conf"))
    script = moved_if_present(script, "/etc/porelo-host/forge/ca.pem", str(forge_etc / "ca.pem"))
    script = moved_if_present(script, "/etc/porelo-host/forge/central-ca.conf", str(forge_etc / "central-ca.conf"))
    script = moved_if_present(script, "/etc/ssl/certs/ca-certificates.crt", str(etc / "system-ca.pem"))
    script = moved_if_present(
        script, "PATH=/usr/sbin:/usr/bin:/sbin:/bin", f"PATH={bin_dir}:/usr/sbin:/usr/bin:/sbin:/bin"
    )
    script = moved_if_present(script, "work=$(mktemp -d)", f"work=$(mktemp -d -p {temporary})")
    script = moved_if_present(script, "ca_owner=0", f"ca_owner={os.getuid()}")
    command = tmp_path / "porelo-host-push"
    command.write_text(script)
    command.chmod(0o755)

    (bin_dir / "id").write_text(f"#!/bin/sh\ncat {tmp_path / 'uid'}\n")
    (tmp_path / "uid").write_text(f"{person_uid}\n")

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

    (bin_dir / "porelo").write_text(
        f"#!{sys.executable}\n"
        "import os, pathlib, sys\n"
        f"calls = pathlib.Path({str(calls)!r})\n"
        f"vault_calls = pathlib.Path({str(vault_calls)!r})\n"
        "with calls.open('a') as handle:\n"
        "    handle.write('porelo|' + ' '.join(sys.argv[1:]) + '\\n')\n"
        "stdin = sys.stdin.read()\n"
        "with vault_calls.open('a') as handle:\n"
        "    handle.write(\n"
        "        f\"{os.environ.get('HOME', '')}|{os.environ.get('XDG_RUNTIME_DIR', '')}|\"\n"
        "        f\"{' '.join(sys.argv[1:])}|{stdin.replace(chr(10), ',')}\\n\"\n"
        "    )\n"
        f"if pathlib.Path({str(tmp_path / 'vault-missing')!r}).exists():\n"
        "    sys.exit(1)\n"
        f"expected = ['vault', 'credential', '--entry={FORGE_NAME}.person', 'get']\n"
        "if sys.argv[1:] != expected:\n"
        "    sys.exit(2)\n"
        f"if 'protocol=https\\nhost={FORGE_NAME}\\n' not in stdin:\n"
        "    sys.exit(3)\n"
        f"print('username=alice\\npassword={PERSON_TOKEN}')\n"
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
        "opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=ctx), NoRedirect())\n"
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
        "with calls.open('a') as handle:\n"
        "    handle.write(\n"
        "        f\"{os.environ.get('GIT_SSL_CAINFO', '')}|\"\n"
        "        f\"{os.environ.get('GIT_CONFIG_KEY_1', '')}={os.environ.get('GIT_CONFIG_VALUE_1', '')}|\"\n"
        "        f\"{' '.join(args)}\\n\"\n"
        "    )\n"
        "if 'clone' in args and "
        f"pathlib.Path({str(tmp_path / 'clone-says-header')!r}).exists():\n"
        "    sys.stderr.write(os.environ.get('GIT_CONFIG_VALUE_0', '') + '\\n')\n"
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
        f"    arg = re.sub(r'^https://127\\.0\\.0\\.1:[0-9]+/', 'file://{tmp_path / 'local'}/', arg)\n"
        f"    arg = arg.replace('{CENTRAL_BASE}/', 'file://{tmp_path / 'central'}/')\n"
        f"    arg = arg.replace('{ELSEWHERE_BASE}/', 'file://{tmp_path / 'elsewhere'}/')\n"
        "    mapped.append(arg)\n"
        f"os.execv({GIT!r}, [{GIT!r}, *mapped])\n"
    )
    for stub in ("id", "getent", "stat", "runuser", "porelo", "curl", "git"):
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
        "vault_calls": vault_calls,
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


def push(host, *arguments, token=CENTRAL_TOKEN, environment=None, interrupt=False):
    process = subprocess.Popen(
        [str(host["command"]), *arguments],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env={"PATH": "/usr/bin:/bin", "HOME": str(host["decoy_home"]), **(environment or {})},
        text=True,
        start_new_session=True,
    )
    if not interrupt:
        output, _ = process.communicate(token + "\n", timeout=60)
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


def test_a_persons_push_reads_their_own_config_and_vault_token_ignoring_home(host):
    """Prevents pushing with another account's config or $HOME override instead of the caller's own passwd home and vault."""
    central = host["root"] / "central" / "stand-in.git"
    elsewhere = bare(host["root"] / "elsewhere" / "stand-in.git")
    approved = commit(host["local"], host["root"] / "work", "B")

    code, output = push(host, "porelo", "stand-in")

    assert code == 0, f"the push was refused with {code}: {output}"
    assert head(central) == approved, f"asked for central main {approved}, got {head(central)}"
    assert not git("--git-dir", str(elsewhere), "for-each-ref"), "$HOME redirected the push config"
    assert "stand-in: taken" in output, output
    vault_log = host["vault_calls"].read_text() if host["vault_calls"].exists() else ""
    assert (
        f"{host['alice_home']}|/run/user/{host['person_uid']}|"
        f"vault credential --entry={FORGE_NAME}.person get|"
        f"protocol=https,host={FORGE_NAME}"
    ) in vault_log, f"unexpected vault call: {vault_log}"
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
    """Prevents running the developer push as root or under sudo instead of the person's own account."""
    (host["root"] / "uid").write_text("0\n")

    code, output = push(host, "porelo", "stand-in")

    assert code == 77, f"asked for 77 when run as root, got {code}: {output}"
    assert "root" in output, output
    assert "Token" not in output, output
    assert not host["calls"].exists(), "commands ran when root invoked the person push"


def test_a_missing_vault_entry_is_refused_naming_the_entry_and_identities_stop(host):
    """Prevents an unauthenticated clone or opaque failure when the person's forge token is absent from their vault."""
    (host["root"] / "vault-missing").touch()

    code, output = push(host, "porelo", "stand-in")

    assert code == 69, f"asked for 69 on missing vault entry, got {code}: {output}"
    assert f"{FORGE_NAME}.person" in output, output
    assert "porelo-host-stop --stdin identities" in output, output
    assert "Token" not in output, f"asked for central token despite missing local vault entry: {output}"
    git_calls = [
        line
        for line in (host["calls"].read_text().splitlines() if host["calls"].exists() else [])
        if not line.startswith("porelo|")
    ]
    assert not git_calls, f"git ran without the person's vault token: {git_calls}"


@pytest.mark.parametrize("stage", ["clone", "push"])
def test_what_git_says_is_shown_without_any_token(host, stage):
    """Prevents either the person's local token or central token from reaching the terminal when git repeats a header."""
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
    lines = [
        line.split("|", 2)
        for line in host["calls"].read_text().splitlines()
        if not line.startswith(("porelo|", "curl|"))
    ]
    remote = [call for call in lines if any(f" {verb} " in f" {call[2]} " for verb in ("clone", "push", "fetch"))]
    assert remote, f"no call reached a forge: {lines}"
    for ca, redirects, line in remote:
        assert redirects == "http.followRedirects=false", f"a forge call follows redirects: {line}"
        want = forge_etc / ("ca.pem" if line.startswith("clone") else "central-ca.pem")
        assert ca == str(want), f"asked for {want} for {line!r}, got {ca!r}"


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
    """Prevents --check from reading stdin through a symlinked admin token file or proceeding without the admin token."""
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
        code, output = push(host, "--migrate", "porelo")

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
    code, output = push(host, "--migrate", "porelo")
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
