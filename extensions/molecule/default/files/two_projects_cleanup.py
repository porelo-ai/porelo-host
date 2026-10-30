"""Remove what two_projects.py made, whatever stage it reached, so side_effect's down finds no one.

Each step runs even when one before it failed; the JSON line names the steps that failed, never their words, except
the host tools' own refusal line, which names no secret.
"""

import json
import pathlib
import pwd
import shutil
import ssl
import subprocess
import urllib.error
import urllib.request

PROJECTS = {"gamma-one": "ga", "gamma-two": "gb"}
PEOPLE = ("gd", "ga", "gb")
failures = {}

forge_token = pathlib.Path("/home/porelo-forge/.config/porelo-forge/api.token").read_text(encoding="utf-8").strip()
forge_uid = pwd.getpwnam("porelo-forge").pw_uid
context = ssl.create_default_context(cafile="/etc/porelo-host/forge/ca.pem")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=context))


def delete(path):
    request = urllib.request.Request(
        "https://10.73.7.1:3000/api/v1" + path, method="DELETE", headers={"Authorization": "token " + forge_token}
    )
    try:
        with opener.open(request, timeout=30):
            return
    except urllib.error.HTTPError as error:
        error.close()
        if error.code != 404:
            failures[path] = error.code


def tool(*argv):
    done = subprocess.run(list(argv), input="", capture_output=True, text=True, cwd="/")
    if done.returncode != 0:
        failures[" ".join(argv[:3])] = ((done.stderr or "").strip().splitlines() or [""])[-1][:300]


for project in PROJECTS:
    delete(f"/repos/{project}/app")
    delete(f"/repos/central-{project}/app")
    delete(f"/orgs/central-{project}")
    if pathlib.Path(f"/etc/porelo-host/projects/{project}.conf").exists():
        tool("/usr/local/sbin/porelo-host-project", "remove", project)

for person in PEOPLE:
    if pathlib.Path(f"/etc/porelo-host/people/{person}.conf").exists():
        tool("/usr/local/sbin/porelo-host-person", "purge", person)
# Forgejo's own command, since the role's token administers no users; it takes the reader's tokens with it.
gone = subprocess.run(
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
        "delete",
        "--username",
        "central-gr",
    ],
    capture_output=True,
    text=True,
    cwd="/",
)
if gone.returncode != 0 and "user does not exist" not in gone.stderr.lower():
    failures["delete central-gr"] = gone.returncode
shutil.rmtree("/root/verify-two", ignore_errors=True)
print(json.dumps({"cleaned": not failures, "failures": failures}))
