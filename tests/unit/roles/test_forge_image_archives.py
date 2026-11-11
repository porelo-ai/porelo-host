"""Keep the forge's pinned images loadable from archives: before the pull, and only the pinned digest."""

import io
import json
import os
import subprocess
import tarfile
from pathlib import Path

import yaml

HERE = Path(__file__).parent
ROOT = HERE.parents[2]
ROLE = ROOT / "roles/forge"
NAME = "codeberg.org/forgejo/forgejo"
DIGEST = "1" * 64
IMAGE = f"{NAME}:17.0.0-rootless@sha256:{DIGEST}"


def tasks(name):
    return yaml.safe_load((ROLE / "tasks" / name).read_text())


def position(steps, predicate, what):
    found = [index for index, step in enumerate(steps) if predicate(step)]
    assert len(found) == 1, f"{what}: {len(found)} matches"
    return found[0]


def loads(image):
    return lambda step: step.get("vars", {}).get("__forge_archive_image") == "{{ " + image + " }}"


def named(text):
    return lambda step: text in step.get("name", "")


def test_each_pinned_image_is_loaded_before_podman_is_asked_and_before_the_pull():
    """Prevent a pull from a registry that is down when the image's archive is at hand."""
    for file, image, asked, pulled in (
        ("service.yml", "__forge_image", "Ask podman whether Forgejo's image", "Pull Forgejo's image"),
        ("runner.yml", "__forge_runner_image", "Ask podman whether the runner's image", "Pull the runner's image"),
        (
            "runner.yml",
            "__forge_runner_proxy_image",
            "Ask podman whether the runner's proxy image",
            "Pull the runner's proxy image",
        ),
    ):
        steps = tasks(file)
        load = position(steps, loads(image), f"the load of {image}")
        assert load < position(steps, named(asked), asked) < position(steps, named(pulled), pulled)
        assert steps[load]["ansible.builtin.include_tasks"] == "{{ role_path }}/tasks/image.yml"
        assert steps[load]["when"] == "forge_image_archives | length > 0"


def test_skopeo_comes_only_with_archives_and_before_the_first_load():
    """Prevent a host without archives getting a new package, and a load without skopeo."""
    steps = tasks("service.yml")
    install = position(steps, lambda step: step.get("ansible.builtin.apt", {}).get("name") == "skopeo", "skopeo")
    assert steps[install]["when"] == "forge_image_archives | length > 0"
    assert install < position(steps, loads("__forge_image"), "the load of Forgejo's image")


def test_without_archives_the_role_pulls_as_before():
    """Prevent the option changing a host that does not set it."""
    defaults = yaml.safe_load((ROLE / "defaults/main.yml").read_text())
    spec = yaml.safe_load((ROLE / "meta/argument_specs.yml").read_text())
    assert defaults["forge_image_archives"] == ""
    assert spec["argument_specs"]["main"]["options"]["forge_image_archives"]["default"] == ""


def test_the_digest_is_checked_before_podman_and_the_load_is_checked_after():
    """Prevent a wrong archive reaching podman, and a load whose digest did not survive passing silently."""
    steps = tasks("image.yml")
    check = position(steps, named("Stop on an archive whose image is not the pinned one"), "the check")
    asked = position(steps, named("Ask podman whether the image is there already"), "the question")
    block = position(steps, lambda step: "block" in step, "the load")
    assert check < asked < block
    inner = [step["name"] for step in steps[block]["block"]]
    assert inner.index("image | Load the image into the account's podman by its pinned digest") < inner.index(
        "image | Ask podman whether the loaded image answers to its pin"
    )


def archive(directory, digests, digest_name=DIGEST):
    """An OCI archive whose index names the given digests, filed under digest_name as the cache files it."""
    directory.mkdir(exist_ok=True)
    index = json.dumps(
        {
            "schemaVersion": 2,
            "manifests": [
                {"mediaType": "application/vnd.oci.image.index.v1+json", "digest": f"sha256:{d}", "size": 1}
                for d in digests
            ],
        }
    ).encode()
    with tarfile.open(directory / f"{digest_name}.tar", "w") as tar:
        for name, content in (("oci-layout", b'{"imageLayoutVersion": "1.0.0"}'), ("index.json", index)):
            entry = tarfile.TarInfo(name)
            entry.size = len(content)
            tar.addfile(entry, io.BytesIO(content))


def fakes(tmp_path, there):
    """podman and skopeo that only record: the image is there when `there`, or once skopeo copied it."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    state = tmp_path / "state"
    state.mkdir()
    if there:
        (state / "loaded").touch()
    (bin_dir / "podman").write_text(
        # As the real one, `podman unshare <command>` runs the command inside the account's user namespace.
        f'#!/bin/sh\necho "$*" >> {state}/podman\n'
        f'if [ "$1" = unshare ]; then shift; exec "$@"; fi\n'
        f'[ -e {state}/loaded ] && [ "$*" = "image exists {IMAGE}" ]\n'
    )
    (bin_dir / "skopeo").write_text(
        f'#!/bin/sh\nprintf "%s\\n" "$@" > {state}/skopeo\n'
        f'[ -f "${{4#oci-archive:}}" ] || exit 1\n[ -z "$LOADS" ] || touch {state}/loaded\n'
    )
    for tool in ("podman", "skopeo"):
        (bin_dir / tool).chmod(0o755)
    return bin_dir, state


def run(tmp_path, bin_dir, loads_image=True):
    return subprocess.run(
        [
            "ansible-playbook",
            "-i",
            "localhost,",
            str(HERE / "plays/image_archive.yml"),
            "-e",
            json.dumps(
                {
                    "ansible_become": False,
                    "forge_image_archives": str(tmp_path / "images"),
                    "__forge_archive_image": IMAGE,
                }
            ),
        ],
        env=dict(
            os.environ,
            ANSIBLE_NOCOLOR="1",
            PATH=f"{bin_dir}:{os.environ['PATH']}",
            LOADS="yes" if loads_image else "",
        ),
        capture_output=True,
        text=True,
        check=False,
    )


def test_an_archive_of_another_digest_is_refused_before_podman_is_asked(tmp_path):
    """Prevent an archive filed under the pin but holding another image from being loaded."""
    archive(tmp_path / "images", ["2" * 64])
    bin_dir, state = fakes(tmp_path, there=False)
    done = run(tmp_path, bin_dir)
    output = done.stdout + done.stderr
    assert done.returncode != 0, output
    assert f"not the pinned sha256:{DIGEST}" in output and "2" * 64 in output
    assert not (state / "podman").exists() and not (state / "skopeo").exists()


def test_an_archive_naming_several_images_is_refused(tmp_path):
    """Prevent skopeo choosing among images when only the pinned one may be loaded."""
    archive(tmp_path / "images", [DIGEST, "2" * 64])
    bin_dir, state = fakes(tmp_path, there=False)
    done = run(tmp_path, bin_dir)
    assert done.returncode != 0, done.stdout + done.stderr
    assert not (state / "skopeo").exists()


def test_without_the_archive_nothing_is_asked_and_the_pull_follows(tmp_path):
    """Prevent a missing archive failing the up: the image is pulled as before."""
    archive(tmp_path / "images", ["2" * 64], digest_name="2" * 64)
    bin_dir, state = fakes(tmp_path, there=False)
    done = run(tmp_path, bin_dir)
    assert done.returncode == 0, done.stdout + done.stderr
    assert not (state / "podman").exists() and not (state / "skopeo").exists()


def test_the_pinned_archive_is_loaded_under_its_name_and_digest_and_its_copy_removed(tmp_path):
    """Prevent a load that keeps no repository digest, which the pull after it would not see."""
    archive(tmp_path / "images", [DIGEST])
    bin_dir, state = fakes(tmp_path, there=False)
    done = run(tmp_path, bin_dir)
    assert done.returncode == 0, done.stdout + done.stderr
    argv = (state / "skopeo").read_text().splitlines()
    assert argv[:3] == ["copy", "--quiet", "--preserve-digests"]
    assert argv[4] == f"containers-storage:{NAME}@sha256:{DIGEST}"
    copy = Path(argv[3].removeprefix("oci-archive:"))
    assert copy.name == "image.tar" and copy.parent.parent == Path("/var/tmp") and not copy.parent.exists()
    # skopeo inside podman's user namespace, since Ubuntu lets podman, not skopeo, open one for the account.
    load = "unshare skopeo " + " ".join(argv)
    assert (state / "podman").read_text().splitlines() == [f"image exists {IMAGE}", load, f"image exists {IMAGE}"]


def test_a_load_whose_digest_podman_does_not_find_fails(tmp_path):
    """Prevent the pull quietly fetching what the archive should have brought."""
    archive(tmp_path / "images", [DIGEST])
    bin_dir, state = fakes(tmp_path, there=False)
    done = run(tmp_path, bin_dir, loads_image=False)
    assert done.returncode != 0, done.stdout + done.stderr
    assert (state / "skopeo").exists()
    copy = Path((state / "skopeo").read_text().splitlines()[3].removeprefix("oci-archive:"))
    assert not copy.parent.exists()


def test_an_image_already_there_is_not_loaded_again(tmp_path):
    """Prevent a second up changing anything, as Molecule's idempotence asks."""
    archive(tmp_path / "images", [DIGEST])
    bin_dir, state = fakes(tmp_path, there=True)
    done = run(tmp_path, bin_dir)
    assert done.returncode == 0, done.stdout + done.stderr
    assert not (state / "skopeo").exists()
    assert "changed=0" in done.stdout
