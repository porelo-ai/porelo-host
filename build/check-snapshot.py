#!/usr/bin/env python3
"""Checks a published snapshot collection: latest.json names a tarball that is there with its digest, and SHA256SUMS
names that tarball exactly once with the same digest. Reads a directory, so the Build checks its files before the upload
and again after fetching them anonymously.

usage: build/check-snapshot.py <directory holding latest.json, SHA256SUMS and the tarball>
"""

import hashlib
import json
import re
import sys
from pathlib import Path

VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+-snapshot\.[0-9]+")
DIGEST = re.compile(r"[0-9a-f]{64}")
COMMIT = re.compile(r"[0-9a-f]{40}")


def fail(message):
    print(f"FAILED: {message}", file=sys.stderr)
    sys.exit(1)


def pointer(directory):
    """latest.json, every field well formed, its file named by its version alone."""
    try:
        record = json.loads((directory / "latest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        fail(f"latest.json could not be read as JSON: {error}")
    if not isinstance(record, dict) or set(record) != {"version", "file", "sha256", "commit"}:
        fail(f"latest.json must hold exactly version, file, sha256 and commit; got {record!r}")
    for field, form in (("version", VERSION), ("sha256", DIGEST), ("commit", COMMIT)):
        if not isinstance(record[field], str) or not form.fullmatch(record[field]):
            fail(f"latest.json's {field} must match {form.pattern}; got {record[field]!r}")
    expected = f"porelo-host-{record['version']}.tar.gz"
    if record["file"] != expected:
        fail(f"latest.json's file must be {expected}; got {record['file']!r}")
    return record


def listed(directory, name):
    """The one digest SHA256SUMS gives for name."""
    try:
        lines = (directory / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    except OSError as error:
        fail(f"SHA256SUMS could not be read: {error}")
    digests = [line.split()[0] for line in lines if len(line.split()) == 2 and line.split()[1].lstrip("*") == name]
    if len(digests) != 1:
        fail(f"SHA256SUMS must name {name} exactly once; it names it {len(digests)} times")
    return digests[0]


def main(arguments):
    if len(arguments) != 1:
        fail("usage: check-snapshot.py <directory>")
    directory = Path(arguments[0])
    record = pointer(directory)
    try:
        actual = hashlib.sha256((directory / record["file"]).read_bytes()).hexdigest()
    except OSError as error:
        fail(f"{record['file']} could not be read: {error}")
    if actual != record["sha256"]:
        fail(f"{record['file']}: latest.json asked for sha256 {record['sha256']}; the file has {actual}")
    named = listed(directory, record["file"])
    if named != record["sha256"]:
        fail(f"{record['file']}: latest.json asked for sha256 {record['sha256']}; SHA256SUMS gives {named}")
    print(f"OK    {record['file']} sha256 {actual}, commit {record['commit']}")


if __name__ == "__main__":
    main(sys.argv[1:])
