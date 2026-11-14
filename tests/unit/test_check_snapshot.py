"""Guard the published snapshot collection against a pointer or a digest list that names another file than is there."""

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "build/check-snapshot.py"
VERSION = "0.5.13-snapshot.412"
FILE = f"porelo-host-{VERSION}.tar.gz"
COMMIT = "a" * 40


def published(directory, *, content=b"the collection", sums=None, pointer=None):
    """A directory as the pre-release holds it: the tarball, SHA256SUMS and latest.json."""
    directory.mkdir()
    (directory / FILE).write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    older = "b" * 64 + "  porelo-host-0.5.13-snapshot.411.tar.gz\n"
    (directory / "SHA256SUMS").write_text(older + f"{digest}  {FILE}\n" if sums is None else sums)
    record = {"version": VERSION, "file": FILE, "sha256": digest, "commit": COMMIT}
    (directory / "latest.json").write_text(json.dumps(record) if pointer is None else pointer)
    return directory


def check(directory):
    return subprocess.run([str(CHECK), str(directory)], capture_output=True, text=True, check=False)


def test_a_pointer_whose_file_and_digests_agree_passes(tmp_path):
    directory = published(tmp_path / "snapshot")
    done = check(directory)
    assert done.returncode == 0, done.stderr
    assert FILE in done.stdout, "the check names the file it believed"


def test_a_pointer_naming_another_digest_fails(tmp_path):
    """Prevent a window's build taking a file the pointer did not describe."""
    directory = published(tmp_path / "snapshot", pointer=None)
    record = json.loads((directory / "latest.json").read_text())
    record["sha256"] = "c" * 64
    (directory / "latest.json").write_text(json.dumps(record))
    done = check(directory)
    assert done.returncode != 0, "a pointer with another digest must fail"
    assert "c" * 64 in done.stderr, "the failure says what it asked"


def test_a_file_changed_after_its_digest_was_written_fails(tmp_path):
    """Prevent a replaced tarball passing under the digest of the one before."""
    directory = published(tmp_path / "snapshot")
    (directory / FILE).write_bytes(b"another collection")
    assert check(directory).returncode != 0, "a changed file must fail"


@pytest.mark.parametrize(
    "sums",
    [
        "b" * 64 + "  porelo-host-0.5.13-snapshot.411.tar.gz\n",
        "{d}  " + FILE + "\n{d}  " + FILE + "\n",
        "d" * 64 + "  " + FILE + "\n",
    ],
    ids=["without the file", "naming it twice", "with another digest"],
)
def test_a_digest_list_that_does_not_name_the_file_once_with_its_digest_fails(tmp_path, sums):
    """Prevent SHA256SUMS and the pointer disagreeing, which a fetch that reads either would trust."""
    content = b"the collection"
    sums = sums.replace("{d}", hashlib.sha256(content).hexdigest())
    directory = published(tmp_path / "snapshot", content=content, sums=sums)
    assert check(directory).returncode != 0, "SHA256SUMS must name the file exactly once with its digest"


@pytest.mark.parametrize(
    "pointer",
    [
        "not json",
        json.dumps({"version": VERSION, "file": "../" + FILE, "sha256": "e" * 64, "commit": COMMIT}),
        json.dumps({"version": VERSION, "file": FILE, "sha256": "E" * 64, "commit": COMMIT}),
        json.dumps({"version": VERSION, "file": "porelo-host-0.5.13.tar.gz", "sha256": "e" * 64, "commit": COMMIT}),
        json.dumps({"version": VERSION, "file": FILE, "sha256": "e" * 64}),
    ],
    ids=["no json", "a path", "an upper-case digest", "a file of another version", "no commit"],
)
def test_a_pointer_that_is_not_well_formed_fails(tmp_path, pointer):
    """Prevent a pointer leading a fetch out of the place or to a name it does not version."""
    directory = published(tmp_path / "snapshot", pointer=pointer)
    assert check(directory).returncode != 0, "a pointer that is not well formed must fail"
