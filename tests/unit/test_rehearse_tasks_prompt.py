"""Keep the rehearsal's task pair answering each line as it arrives, so the busy room's waits measure delivery."""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STEP = ROOT / "build/rehearse-steps/tasks"


def prompt():
    script = STEP.read_text(encoding="utf-8")
    assignment = re.search(r'^prompt="(?:[^"\\]|\\.)*"$', script, re.MULTILINE | re.DOTALL)
    assert assignment, "the tasks step sets no prompt"
    done = subprocess.run(
        ["sh", "-c", f'answer_minutes=60\n{assignment.group(0)}\nprintf "%s" "$prompt"'],
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout


def test_a_task_answers_every_new_line_before_it_sleeps_again():
    """Prevent a task finishing its sleep and a second read before it answers, which the busy room counts as silence."""
    text = prompt()
    assert "answer at once" in text, text
    assert text.index("answer at once") < text.index("sleep 20"), text
    assert text.count("sleep 20") == 1, text


def test_the_prompt_keeps_what_a_task_must_never_do():
    """Prevent the reworded prompt dropping the limits the rehearsal relies on."""
    text = prompt()
    for kept in ("Never answer a line that names only another agent", "Change no file and push nothing", "60 minutes"):
        assert kept in text, text
