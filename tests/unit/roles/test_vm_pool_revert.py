"""Prevent a pool VM being handed out with its base snapshot's clock, set back by every revert."""

import fcntl
import os
import subprocess
import time
from pathlib import Path

SCRIPT = Path(__file__).parents[3] / "roles/vm_pool/files/porelo-pool-revert"
MAC = "52:54:00:aa:bb:cc"
REVERT = "snapshot-revert pool-1 base --paused"
LINK_DOWN = f"domif-setlink pool-1 {MAC} down"
RESUME = "resume pool-1"
CLOCK = "domtime pool-1 --now"
LINK_UP = f"domif-setlink pool-1 {MAC} up"


def prepared(tmp_path, args, said):
    """Stub virsh, sleep and timeout, and say how the real script runs over them."""
    answers = {
        "domstate": 'echo "shut off"',
        "domtime": "exit 0",
        "snapshot": "exit 0",
        "link": "exit 0",
        "resume": "exit 0",
        "destroy": "exit 0",
        "getlink": f'echo "{MAC} up"',
        "event": "exit 0",
    } | said
    (tmp_path / "vms").write_text("pool-1\n")
    calls = tmp_path / "calls"
    stubs = tmp_path / "stubs"
    stubs.mkdir(exist_ok=True)
    virsh = stubs / "virsh"
    virsh.write_text(f"""#!/bin/sh
echo "$*" >> {calls}
case "$1" in
domstate) {answers["domstate"]} ;;
domiflist) printf ' Interface Type Source Model MAC\\n---\\n vnet0 network default virtio {MAC}\\n\\n' ;;
domif-getlink) {answers["getlink"]} ;;
domif-setlink) {answers["link"]} ;;
domtime) {answers["domtime"]} ;;
snapshot-revert) {answers["snapshot"]} ;;
resume) {answers["resume"]} ;;
destroy) {answers["destroy"]} ;;
event) {answers["event"]} ;;
esac
""")
    virsh.chmod(0o755)
    sleep = stubs / "sleep"
    sleep.write_text("#!/bin/sh\n")
    sleep.chmod(0o755)
    # What the script's own limit of an unanswered agent would wait, cut short.
    limit = stubs / "timeout"
    limit.write_text('#!/bin/sh\nshift\nexec /usr/bin/timeout 0.05 "$@"\n')
    limit.chmod(0o755)
    run = tmp_path / "run"
    run.mkdir(exist_ok=True)
    return (
        ["sh", str(SCRIPT), *(args or [str(tmp_path / "vms")])],
        dict(os.environ, PATH=f"{stubs}{os.pathsep}{os.environ['PATH']}", RUNTIME_DIRECTORY=str(run)),
        calls,
    )


def revert(tmp_path, *, args=None, midway=False, **said):
    """Run the real script until its watch ends, over one VM and a virsh that answers as told."""
    command, env, calls = prepared(tmp_path, args, said)
    if midway:
        (tmp_path / "run" / "pool-1.midway").touch()
    done = subprocess.run(command, env=env, capture_output=True, text=True, check=False)
    return done, calls.read_text().splitlines()


def test_a_reverted_vm_cannot_be_reached_until_its_clock_is_the_hosts(tmp_path):
    """Prevent a rental reading the snapshot's 'ready' in the moment before the clock is set."""
    done, calls = revert(tmp_path)
    steps = [calls.index(step) for step in (REVERT, LINK_DOWN, RESUME, CLOCK, LINK_UP)]
    assert steps == sorted(steps), calls
    assert "destroy pool-1" not in calls
    assert "reverted pool-1 to its base snapshot" in done.stdout


def test_a_clock_that_stays_late_a_moment_is_asked_again(tmp_path):
    marker = tmp_path / "once"
    calls = revert(tmp_path, domtime=f"[ -e {marker} ] || {{ touch {marker}; exit 1; }}")[1]
    assert calls.count(CLOCK) == 2
    assert LINK_UP in calls
    assert "destroy pool-1" not in calls


def test_a_clock_that_cannot_be_set_says_so_and_the_vm_is_not_handed_out(tmp_path):
    done, calls = revert(tmp_path, domtime="exit 1")
    assert "destroy pool-1" in calls
    assert LINK_UP not in calls
    assert "could not set the clock of pool-1" in done.stderr and "not handed out" in done.stderr


def test_a_vm_that_cannot_be_stopped_either_says_its_link_stays_down(tmp_path):
    """Prevent saying a VM stays off that is still running."""
    done, calls = revert(tmp_path, domtime="exit 1", destroy="exit 1")
    assert LINK_UP not in calls
    assert "stays off" not in done.stderr
    assert "could not stop pool-1" in done.stderr and "link stays down" in done.stderr


def test_a_link_that_cannot_go_down_gives_no_vm_reachable_with_the_old_clock(tmp_path):
    calls = revert(tmp_path, link="exit 1")[1]
    assert RESUME not in calls
    assert "destroy pool-1" in calls


def test_a_vm_whose_clock_cannot_be_set_is_not_reverted_over_and_over(tmp_path):
    """Prevent its own stop, which the service watches, starting the same failing revert for ever."""
    event = "echo \"event 'lifecycle' for domain 'pool-1': Stopped Destroyed\""
    calls = revert(tmp_path, domtime="exit 1", event=event)[1]
    assert calls.count(REVERT) == 1


def test_a_restarted_service_tries_a_vm_left_off_again(tmp_path):
    calls = revert(tmp_path, domtime="exit 1")[1]
    assert calls.count(REVERT) == 1
    calls = revert(tmp_path, domtime="exit 1")[1]
    assert calls.count(REVERT) == 2


def test_a_stopped_vm_is_reverted_when_the_watch_says_so(tmp_path):
    """Prevent the rounds' looks hiding a watch that reads no event."""
    stopped = tmp_path / "stopped"
    state = f'if [ -e {stopped} ]; then echo "shut off"; else echo running; fi'
    event = (
        f"until grep -q domstate {tmp_path}/calls; do /usr/bin/sleep 0.01; done; touch {stopped}; "
        "echo \"event 'lifecycle' for domain 'pool-1': Stopped Shutdown\""
    )
    calls = revert(tmp_path, domstate=state, event=event)[1]
    assert calls.count("event --loop --timeout 30 --event lifecycle") == 1
    assert REVERT in calls


def test_a_retry_clears_the_old_failure_before_its_link_comes_up(tmp_path):
    """Prevent a VM reachable and rented, once given back, being skipped for an old failure."""
    revert(tmp_path, domtime="exit 1")
    calls = tmp_path / "calls"
    off = tmp_path / "run" / "pool-1.off"
    assert off.exists()
    answer = f"[ ! -e {off} ] || {{ echo the-marker-outlived-the-retry >> {calls}; exit 1; }}"
    calls_after = revert(tmp_path, args=["--one", "pool-1"], link=f'case "$3" in up) {answer} ;; esac')[1]
    assert "the-marker-outlived-the-retry" not in calls_after


def test_a_failed_revert_still_says_so_and_asks_no_clock(tmp_path):
    done, calls = revert(tmp_path, snapshot="exit 1")
    assert "could not revert pool-1" in done.stderr
    assert not [call for call in calls if call.startswith("domtime")]


def test_a_revert_left_midway_by_a_stopped_service_is_done_again(tmp_path):
    """Prevent a VM staying unreachable for ever when the service ended between link down and link up."""
    gone = tmp_path / "gone"
    state = f'if [ -e {gone} ]; then echo "shut off"; else echo running; fi'
    calls = revert(tmp_path, midway=True, domstate=state, getlink=f'echo "{MAC} down"', destroy=f"touch {gone}")[1]
    assert calls.index("destroy pool-1") < calls.index(REVERT)
    assert LINK_UP in calls


def test_a_paused_vm_left_by_a_stopped_service_is_done_again(tmp_path):
    gone = tmp_path / "gone"
    state = f'if [ -e {gone} ]; then echo "shut off"; else echo paused; fi'
    calls = revert(tmp_path, midway=True, domstate=state, destroy=f"touch {gone}")[1]
    assert calls.index("destroy pool-1") < calls.index(REVERT)


def test_a_paused_vm_no_revert_left_is_not_destroyed(tmp_path):
    """Prevent a rented VM that libvirt paused on a disk error losing its renter's work."""
    calls = revert(tmp_path, domstate="echo paused")[1]
    assert "destroy pool-1" not in calls
    assert REVERT not in calls


def test_a_vm_with_its_link_down_no_revert_left_is_not_destroyed(tmp_path):
    calls = revert(tmp_path, domstate="echo running", getlink=f'echo "{MAC} down"')[1]
    assert "destroy pool-1" not in calls


def test_a_running_vm_with_its_link_up_is_left_alone(tmp_path):
    calls = revert(tmp_path, midway=True, domstate="echo running")[1]
    assert "destroy pool-1" not in calls
    assert REVERT not in calls
    assert not (tmp_path / "run" / "pool-1.midway").exists()


def test_a_revert_that_cannot_record_itself_does_not_begin(tmp_path):
    """Prevent a VM going down its link with nothing to say that a revert left it so."""
    command, env, calls = prepared(tmp_path, None, {})
    (tmp_path / "run").rmdir()
    done = subprocess.run(command, env=env, capture_output=True, text=True, check=False)
    assert REVERT not in calls.read_text()
    assert "pool-1" in done.stderr


def test_a_link_that_cannot_be_read_keeps_the_note_of_a_revert_left_midway(tmp_path):
    """Prevent one failed question leaving a VM with its link down and nothing to say a revert left it so."""
    done, calls = revert(tmp_path, midway=True, domstate="echo running", getlink="exit 1")
    assert (tmp_path / "run" / "pool-1.midway").exists()
    assert "destroy pool-1" not in calls
    assert "could not read how pool-1 stands" in done.stderr


def test_a_nic_that_cannot_be_read_keeps_the_note_of_a_revert_left_midway(tmp_path):
    command, env = prepared(tmp_path, ["--one", "pool-1"], {"domstate": "echo running"})[:2]
    (tmp_path / "run" / "pool-1.midway").touch()
    stub = tmp_path / "stubs" / "virsh"
    stub.write_text(stub.read_text().replace("domiflist) printf", "domiflist) exit 1; printf"))
    done = subprocess.run(command, env=env, capture_output=True, text=True, check=False)
    assert done.returncode == 1
    assert (tmp_path / "run" / "pool-1.midway").exists()


def test_a_revert_that_failed_but_left_the_vm_paused_is_done_again(tmp_path):
    """Prevent a client killed after libvirt's restore leaving a paused VM nobody takes up again."""
    tried = tmp_path / "tried"
    gone = tmp_path / "gone"
    state = f'if [ -e {tried} ] && [ ! -e {gone} ]; then echo paused; else echo "shut off"; fi'
    snapshot = f"[ -e {tried} ] && exit 0; touch {tried}; exit 1"
    # The second round finds it paused, with the note still there.
    seen = tmp_path / "seen"
    event = f'[ -e {seen} ] && exit 1; touch {seen}; echo "event loop timed out"; exit 1'
    calls = revert(tmp_path, domstate=state, snapshot=snapshot, destroy=f"touch {gone}", event=event)[1]
    assert "destroy pool-1" in calls
    assert calls.count(REVERT) == 2
    assert LINK_UP in calls


def test_a_state_read_that_fails_once_keeps_the_note_of_a_revert_left_midway(tmp_path):
    """Prevent one failed question leaving a paused VM that nothing takes up again."""
    asked = tmp_path / "asked"
    state = f"[ -e {asked} ] && {{ echo paused; exit 0; }}; touch {asked}; exit 1"
    done, calls = revert(tmp_path, args=["--one", "pool-1"], midway=True, domstate=state)
    assert done.returncode == 1
    assert (tmp_path / "run" / "pool-1.midway").exists()
    assert "destroy pool-1" not in calls


def test_a_state_that_cannot_be_read_fails_up(tmp_path):
    """Prevent up taking a libvirt that does not answer for a VM with nothing to do."""
    done = revert(tmp_path, args=["--one", "pool-1"], domstate="exit 1")[0]
    assert done.returncode == 1
    assert "could not read the state of pool-1" in done.stderr


def test_a_lock_held_too_long_is_said_and_fails_up(tmp_path):
    """Prevent up waiting for ever behind a revert that hangs."""
    command, env = prepared(tmp_path, ["--one", "pool-1"], {})[:2]
    stub = tmp_path / "stubs" / "flock"
    stub.write_text("#!/bin/sh\nexit 1\n")
    stub.chmod(0o755)
    done = subprocess.run(command, env=env, capture_output=True, text=True, check=False)
    assert done.returncode == 1
    assert "another revert" in done.stderr


def test_a_stop_the_watch_missed_is_found_by_its_next_round(tmp_path):
    """Prevent a VM that stopped before the watch was connected staying off for good."""
    seen = tmp_path / "seen"
    stopped = tmp_path / "stopped"
    state = f'if [ -e {stopped} ]; then echo "shut off"; else echo running; fi'
    # The first round's look sees it running; it stops, unseen; the round times out, as virsh says it; the next ends all.
    event = (
        f"[ ! -e {seen} ] || exit 1; until grep -q domstate {tmp_path}/calls; do /usr/bin/sleep 0.01; done; "
        f'touch {seen} {stopped}; echo "event loop timed out"; exit 1'
    )
    done, calls = revert(tmp_path, domstate=state, event=event)
    assert calls.count(REVERT) == 1
    assert "virsh event ended" in done.stderr


def test_a_watch_that_fails_ends_the_service(tmp_path):
    """Prevent a service that watches nothing looking as if it did; systemd starts it again."""
    done, calls = revert(tmp_path, event="exit 1")
    assert done.returncode == 1
    assert calls.count("event --loop --timeout 30 --event lifecycle") == 1


def test_an_agent_that_never_answers_does_not_hold_up_the_pool(tmp_path):
    """Prevent one VM's silent agent stopping every other VM's revert; libvirt waits for it for ever."""
    done = revert(tmp_path, domtime="exec /usr/bin/sleep 30")[0]
    assert "could not set the clock of pool-1" in done.stderr


def test_two_reverts_of_the_pool_take_turns(tmp_path):
    """Prevent up's revert raising the link of a VM the service has just taken down, with the old clock."""
    command, env, calls = prepared(tmp_path, ["--one", "pool-1"], {})
    # The directory, not the script: the role's replacing the script gives its path another inode, and another lock.
    tools = os.open(SCRIPT.parent, os.O_RDONLY)
    try:
        fcntl.flock(tools, fcntl.LOCK_EX)
        running = subprocess.Popen(command, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.5)
        assert not calls.exists() or REVERT not in calls.read_text()
        fcntl.flock(tools, fcntl.LOCK_UN)
    finally:
        os.close(tools)
    assert running.wait(timeout=30) == 0
    assert REVERT in calls.read_text()


def test_one_vm_for_up_fails_loud_and_watches_nothing(tmp_path):
    done, calls = revert(tmp_path, args=["--one", "pool-1"], domtime="exit 1")
    assert done.returncode == 1
    assert "could not set the clock of pool-1" in done.stderr
    assert not [call for call in calls if call.startswith("event")]


def test_one_vm_for_up_does_again_what_a_stopped_service_left_midway(tmp_path):
    """Prevent up failing for good on a VM it can neither reach nor would revert, with the service stopped."""
    gone = tmp_path / "gone"
    state = f'if [ -e {gone} ]; then echo "shut off"; else echo paused; fi'
    done, calls = revert(tmp_path, args=["--one", "pool-1"], midway=True, domstate=state, destroy=f"touch {gone}")
    assert done.returncode == 0
    assert calls.index("destroy pool-1") < calls.index(REVERT)


def test_one_vm_for_up_leaves_a_running_vm_alone(tmp_path):
    """Prevent up reverting a VM the service has handed out since up looked."""
    done, calls = revert(tmp_path, args=["--one", "pool-1"], domstate="echo running")
    assert done.returncode == 0
    assert REVERT not in calls
    assert "reverted" not in done.stdout


def test_one_vm_for_up_tries_a_vm_left_off_again_and_clears_it(tmp_path):
    """Prevent a VM up brought back staying off at its next stop, by the marker of its old failure."""
    revert(tmp_path, domtime="exit 1")
    done, calls = revert(tmp_path, args=["--one", "pool-1"])
    assert done.returncode == 0
    assert LINK_UP in calls
    assert not (tmp_path / "run" / "pool-1.off").exists()
