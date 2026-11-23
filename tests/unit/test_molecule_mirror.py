"""Keep a Molecule run from hanging on an Ubuntu mirror that does not answer, and let CI name one that does."""

import os
import subprocess
from pathlib import Path

import jinja2
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


def converge_tasks():
    return yaml.safe_load((ROOT / "extensions/molecule/default/converge.yml").read_text())[0]["tasks"]


def named(tasks, name):
    found = [index for index, item in enumerate(tasks) if item.get("name") == name]
    assert len(found) == 1, name
    return found[0]


def test_apt_gives_up_on_a_silent_mirror_before_ansible_core_is_installed():
    tasks = converge_tasks()
    limits = named(tasks, "Make apt give up on a mirror that does not answer")
    install = named(tasks, "Install Ubuntu's own ansible-core")
    assert limits < install, "apt's limits stand before its first download"
    content = tasks[limits]["ansible.builtin.copy"]["content"]
    for line in ['Acquire::http::Timeout "20";', 'Acquire::https::Timeout "20";', 'Acquire::Retries "2";']:
        assert line in content, line


def test_the_ansible_core_install_stops_loudly_within_ten_minutes():
    tasks = converge_tasks()
    assert tasks[named(tasks, "Install Ubuntu's own ansible-core")]["timeout"] == 600


CHAIN = (
    "http://azure.archive.ubuntu.com/ubuntu/ http://archive.ubuntu.com/ubuntu/ "
    "http://mirrors.edge.kernel.org/ubuntu/ http://ftp.fau.de/ubuntu/"
)


def test_the_vm_takes_the_mirror_chain_the_run_names_in_its_order_and_only_then():
    tasks = converge_tasks()
    install = named(tasks, "Install Ubuntu's own ansible-core")
    listed = named(tasks, "Write the mirror chain the run names, first tried first")
    use = named(tasks, "Point the VM's Ubuntu sources at that mirror chain")
    assert listed < use < install
    for index in (listed, use):
        assert tasks[index]["when"] == "converge_mirrors | length > 0"
    written = tasks[listed]["ansible.builtin.copy"]
    assert written["dest"] == "/etc/apt/porelo-mirrors.txt"
    env = jinja2.Environment(keep_trailing_newline=True)
    text = env.from_string(written["content"]).render(converge_mirrors=CHAIN.split())
    assert text.splitlines() == [f"{mirror}\tpriority:{n}" for n, mirror in enumerate(CHAIN.split(), 1)]
    replace = tasks[use]["ansible.builtin.replace"]
    assert replace["path"] == "/etc/apt/sources.list.d/ubuntu.sources"
    assert replace["regexp"] == "^URIs: .*$" and replace["replace"] == "URIs: mirror+file:/etc/apt/porelo-mirrors.txt"
    play = yaml.safe_load((ROOT / "extensions/molecule/default/converge.yml").read_text())[0]
    assert "PORELO_HOST_MOLECULE_MIRRORS" in play["vars"]["converge_mirrors"]


def test_ci_names_the_runners_mirror_then_ubuntus_then_two_outside_canonical_and_azure():
    build = yaml.safe_load((ROOT / ".github/workflows/build.yml").read_text())
    step = [s for s in build["jobs"]["molecule"]["steps"] if s.get("name") == "The Molecule scenario on its VM"][0]
    assert step["env"]["PORELO_HOST_MOLECULE_MIRRORS"] == CHAIN


@pytest.mark.parametrize(
    "mirror",
    [
        "ftp://azure.archive.ubuntu.com/ubuntu/",
        "http://a,b/ubuntu/",
        "http://x/$(id)/",
        "http://x/ubuntu/\nURIs: y",
        " ",
    ],
)
def test_molecule_refuses_a_chain_that_is_not_plain_http_addresses(tmp_path, mirror):
    environment = {"PATH": os.environ["PATH"], "HOME": str(tmp_path), "PORELO_HOST_MOLECULE_MIRRORS": mirror}
    result = subprocess.run(
        ["sh", str(ROOT / "build/molecule.sh")], env=environment, capture_output=True, text=True, check=False
    )
    assert result.returncode != 0
    assert "PORELO_HOST_MOLECULE_MIRRORS must be" in result.stderr, result.stderr


def test_molecule_takes_a_chain_of_plain_mirror_addresses_and_goes_on(tmp_path):
    environment = {
        "PATH": os.environ["PATH"],
        "HOME": str(tmp_path),
        "PORELO_HOST_MOLECULE_MIRRORS": CHAIN,
    }
    result = subprocess.run(
        ["sh", str(ROOT / "build/molecule.sh")], env=environment, capture_output=True, text=True, check=False
    )
    assert "PORELO_HOST_MOLECULE_MIRRORS" not in result.stderr, result.stderr
    assert "PORELO_HOST_DEB" in result.stderr, "it went on to the package staging, which needs a package"
