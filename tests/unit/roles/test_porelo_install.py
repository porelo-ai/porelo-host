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
