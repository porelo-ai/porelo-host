"""Guard what up installs for the people's Porelo, as porelo-setup.sh would."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]


def test_up_installs_what_porelo_setup_always_installs():
    """Prevent a host whose apt skips recommended packages from giving people a Porelo without filter or networking.

    porelo-host-person makes the account itself, with each person's own subordinate ID range; porelo-setup.sh
    --user would give every person the same one. The packages the script always installs come from up instead.
    """
    tasks = yaml.safe_load((ROOT / "roles/porelo/tasks/install.yml").read_text())
    names = set()
    for task in tasks:
        name = task.get("ansible.builtin.apt", {}).get("name")
        names.update([name] if isinstance(name, str) else name or [])
    assert {"porelo", "porelo-message-sluice-filter", "uidmap", "slirp4netns", "passt"} <= names


def test_up_installs_every_published_agent_as_the_repository_lists_them():
    """Prevent a list kept by hand from missing a new agent, or the acceptance suite's stub from being installed.

    The operator's decision: up installs every published agent package. Each declares Provides: porelo-agent, the
    stub deliberately not, which is how Porelo's setup script and daemon read the repository as the catalogue.
    """
    tasks = yaml.safe_load((ROOT / "roles/porelo/tasks/install.yml").read_text())
    reads = [task for task in tasks if "apt-cache showpkg porelo-agent" in str(task.get("ansible.builtin.command"))]
    assert len(reads) == 1 and reads[0].get("changed_when") is False
    names = [task for task in tasks if reads[0]["register"] in str(task.get("ansible.builtin.set_fact", {}))]
    assert len(names) == 1
    (fact,) = names[0]["ansible.builtin.set_fact"]
    installs = [task for task in tasks if task.get("ansible.builtin.apt", {}).get("name") == "{{ " + fact + " }}"]
    assert len(installs) == 1
    assert tasks.index(reads[0]) < tasks.index(names[0]) < tasks.index(installs[0])
