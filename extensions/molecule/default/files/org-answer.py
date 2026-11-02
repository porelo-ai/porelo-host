#!/usr/bin/python3 -I
"""Writes the answer the stand-in gives, from a short description on the command line, each person's key made once.

usage: org-answer.py REVISION '{"admins": [...], "persons": [...], "revoked": [...],
                                "projects": {"name": {"login": "role"}}}'
"""

import json
import subprocess
import sys
from pathlib import Path

KEYS = Path("/root/verify-org")
SHARED = Path("/usr/local/share/porelo-org-standin")


def key(login):
    path = KEYS / login
    if not path.exists():
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "", "-f", str(path)], check=True)
    return " ".join(path.with_suffix(".pub").read_text(encoding="utf-8").split()[:2])


def fingerprint(login):
    printed = subprocess.run(["ssh-keygen", "-lf", str(KEYS / f"{login}.pub")], check=True, capture_output=True)
    return printed.stdout.decode().split()[1]


revision, wanted = sys.argv[1], json.loads(sys.argv[2])
host = Path("/etc/porelo-host/forge.conf").read_text(encoding="utf-8")
host = next(line[5:] for line in host.splitlines() if line.startswith("host="))
answer = {
    "revision": revision,
    "host_card": {"host": host, "services": {"forge": {"git_port": 3001}}},
    "admins": [
        {"login": login, "key": key(login), "fingerprint": fingerprint(login), "backup": False}
        for login in wanted["admins"]
    ],
    "persons": [
        {
            "login": login,
            "key": key(login),
            "expires": "2030-01-01",
            "revoked": login in wanted.get("revoked", []),
        }
        for login in wanted["persons"]
    ],
    "projects": [
        {
            "project": name,
            "address": f"git@central.example:acme/{name}.git",
            "members": [{"login": login, "role": role, "locked": False} for login, role in members.items()],
            "signing_keys": [
                {
                    "login": login,
                    "role": role,
                    "key": key(login),
                    "valid_from": "2026-01-01",
                    "valid_until": "2030-01-01",
                    "revoked_since": None,
                }
                for login, role in members.items()
            ],
        }
        for name, members in wanted.get("projects", {}).items()
    ],
}
(SHARED / "answer.json").write_text(json.dumps(answer), encoding="utf-8")
(SHARED / "exit").write_text("0\n", encoding="utf-8")
