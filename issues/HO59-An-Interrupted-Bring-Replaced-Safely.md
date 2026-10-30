# HO59 — An Interrupted Bring Replaced Safely

**Status:** Accepted.
**Size:** M - a marker the bring keeps in its setup directory, the replacement rule and a Molecule step that
interrupts a bring, with a VM run; measured M median 63 min.

**What must be true.** A bring that was interrupted leaves its setup directory
`<home>/.local/share/porelo-host/setup/<project>/` in a state the interface and the next bring can recognize. The
interface then replaces it with a new upload, and the next bring runs to its end. Nobody has to work by hand on the
host. A setup directory still in use is never replaced. That is one whose bring runs now, or one another account
could have changed.

## Contract with the interface (proposed, for Agent Frontend)

- The bring writes `bring.state` into the setup directory, the person's own plain file of mode 0600, before its
  first change: `started <UTC>`. After its last step it writes `done <UTC>`. A bring that stops on a refusal writes
  `refused <UTC>`.
- A setup directory without `bring.state`, or with `started` and no bring running as the person, is an interrupted
  one. The interface may then delete the whole directory and upload all three files anew. With `done` or `refused`
  it may do the same. Each new upload is a whole directory, never single files.
- A bring started while another runs for the same project in the same account refuses, naming the one that runs.
- What a bring already did on the host stays valid: the bring is safe to run again, so the new upload's bring
  finishes it.

## To be checked

- Which refusal the next bring gives today after an interrupted upload or bring: a missing or partial file, a
  wrong mode, or a followed commit the new bundle does not descend from.
- Whether a lock (`flock` on `bring.state`) or the person's running `ansible-playbook` tells best that a bring runs.
