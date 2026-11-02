"""The forge role names no central token file."""

from pathlib import Path

FORGE = Path(__file__).resolve().parents[3] / "roles" / "forge"


def test_no_central_token_lies_on_the_host():
    """Prevent a task reading the central token from a file, or migrating with it, instead of the stop's pipe."""
    named = [
        path
        for path in [*FORGE.glob("tasks/*.yml"), *FORGE.glob("vars/*.yml"), *FORGE.glob("defaults/*.yml")]
        if "forge-central.token" in path.read_text() or "forge_central_token" in path.read_text()
    ]
    assert not named, f"a central token file is still named in: {named}"
