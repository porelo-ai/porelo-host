#!/usr/bin/python3 -I
"""Stands in for `porelo org`, whose commands no published Porelo has yet; anything else goes to the real one.

Runs inside the helper's isolated units, so it also proves what those units give: every credential readable under
a dynamic user, and a state directory that lasts. It answers what the act put in the shared directory.
"""

import json
import os
import sys
from pathlib import Path

SHARED = Path("/usr/local/share/porelo-org-standin")
words = sys.argv[1:]
if words[:1] != ["org"]:
    os.execv("/usr/bin/porelo", ["/usr/bin/porelo", *words])


def value(flag):
    return words[words.index(flag) + 1]


if words[1] == "add-read-key":
    if not sys.stdin.read().strip():
        sys.exit("no token on standard input")
    for flag in ("--settings", "--key"):
        Path(value(flag)).read_text(encoding="utf-8")
    print(json.dumps({"revision": None, "added": True}))
elif words[1] == "fetch":
    for flag in ("--settings", "--ssh-key", "--known-hosts", "--pin"):
        Path(value(flag)).read_text(encoding="utf-8")
    kept = Path(os.environ["XDG_STATE_HOME"]) / "seen"
    with kept.open("a", encoding="utf-8") as seen:
        seen.write((value("--since") if "--since" in words else "first") + "\n")
    code = int((SHARED / "exit").read_text(encoding="utf-8"))
    if code:
        sys.stderr.write((SHARED / "words").read_text(encoding="utf-8"))
        sys.exit(code)
    sys.stdout.write((SHARED / "answer.json").read_text(encoding="utf-8"))
elif words[1] == "signers":
    state = json.loads(Path(value("--state")).read_text(encoding="utf-8"))
    project = next(item for item in state["projects"] if item["project"] == value("--project"))
    lines = [f'{item["login"]} namespaces="git" {item["key"]}\n' for item in project["signing_keys"]]
    print(
        json.dumps(
            {
                "project": project["project"],
                "revision": state["revision"],
                "signers": "".join(lines),
                "certifiers": "".join(lines),
            }
        )
    )
else:
    sys.exit(f"the stand-in has no org {words[1]}")
