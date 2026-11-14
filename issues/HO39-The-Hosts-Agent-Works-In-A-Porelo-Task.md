# HO39 — The Host's Agent Works In A Porelo Task

```json
{
  "$schema": "issue-1.json",
  "id": "HO39",
  "title": "The Host's Agent Works In A Porelo Task",
  "state": "Backlog",
  "size": "S",
  "priority": "Medium",
  "rank": 2,
  "blockedBy": ["HO40"],
  "covers": "porelo-host's agent, `Agent Host`, in a Porelo task on the move's host, with a way back: the image from `porelo.yml`."
}
```

**Why this size.** no code of its own: the move's steps for this repository, this issue worked to Review inside the task,
and the way back once.

**What must be true.** porelo-host's own agent, `Agent Host` in the project's room, works in a Porelo task on the
move's host as the project's procedure for an agent's move lays out, with a way back to this machine at any time, since
a fault in the host's setup can stop its own work.

## Plan

- **Before the move,** once [HO40](README.md#ho40) is on `main`:
  - `porelo-host` is named among the repositories of porelo-ai's `project.yml`, with the nickname `Host`, signed by the
    operator; the follow migrates it to the host's forge. No inventory names a repository any more.
  - This repository's `porelo.yml` signed anew on the host by `porelo project sign-repository-file`, since a task's
    image is built from it; its comment that nothing reads it is corrected first.
  - The move's check for this repository is red.
- **The move:** `porelo task start -p <project> -r porelo-host --agent claude`, attended, from the image `porelo.yml`
  names.
- **Inside the task:** the skills fetched and checked, this issue set to Review, the forge's Build read through the
  `forgejo` reader and green, and the agent answering in the room as `Agent Host`.
- **The way back, once:** the task's open work fetched from the host's forge into this machine's checkout, the upstream
  switched back, the local session resumed.
- **Not in the task:** `build/molecule.sh`, `build/rehearse-move.sh` and any VM test, which need KVM and libvirt; `up` or
  `down` on the move's own host; machine credentials. Those stay on this machine, so the agent keeps a session here
  beside the task. The reading by Codex CLI or Antigravity CLI is done from outside, as the procedure says.

## Acceptance

- The task follows `porelo-host` through the gate, its pushes reach the host's Forgejo, and the build there is green
  and read through the `forgejo` reader.
- This issue is taken from start to Review inside the task, and the agent is reached in the room as `Agent Host`, from
  the nickname `Host` on the repository `porelo-host` in porelo-ai's `project.yml`.
- The way back is shown once: the task's open work fetched from the host's forge into this machine's checkout, the
  upstream switched back, the local session resumed, as that procedure's way back says.

## Answered by the operator

- **Where the move runs:** on the rehearsal's VM, as one more repository of pass 2 (operator, 2026-11-06).

## To be checked

- **The repository alone moves.** `porelo-buildtools`, kept by the same agent today, moves on its own, earlier, by an
  issue of that repository's own, with its scheduled workflows held to GitHub first.
- **The task's image** is `porelo.yml`'s: the Ansible tools image by digest with the pinned GraalVM, in which
  `build/tools.sh` runs each tool directly.
