# HO112 — The Project File Reaches A Task On The Host

**Status:** Review.
**Size:** M - one verb of the project helper, the follow calling it once Porelo accepted the file, the documents.

**What must be true.** What a Project Admin files in the project's own repository at the central forge reaches a task on
the host at the next follow. A task reads `project.yml` from the host's forge, whose copy was taken once, so a repository
named or a review changed after the first follow was unknown there, as the rehearsal on a local machine showed.

## Plan

- `porelo-host-project project-advance <project> <repository> <commit> <copy>` brings that repository's local `main` up
  to the newest change of `project.yml` in the commit in the copy. Only forward, and only if nothing else differs: the
  way past the push judge carries no code. It answers `moved`, `moved-unseen`, `up-to-date`, `ahead`, `diverged` or
  `other-changes`.
- It writes in Forgejo's folder inside its container, past the branch rule, then runs Forgejo's own post-receive so its
  pages show the move: `main` stays closed to every push.
- `follow_read_project_file` calls it only after `porelo project verify` accepted that commit, for the project's own
  repository alone; the others keep `central/main` by a person's pull request.
- `diverged` and `other-changes` leave `main` where it is, and `why` says a task here reads an older file. The follow asks
  again each time.
- A project that lists repositories has no task in its own, so that repository takes no merge on the host and `main` follows
  central's commit (`tip`), whatever else it changes. A project that lists none, or lists its own again, keeps merges and
  takes only the signed change (`signed`).
- `doc/local-forge.md` promises `http://127.0.0.1:<git_port>/<project>/<name>.git` as a repository's address on the host.

## Acceptance

- The verb against real Git repositories: each of its answers, a commit that is not the copy's, nothing left behind.
- The follow: no call for a refused file, none when nothing changed, a retry after a refusal, the copy still there.
- The rehearsal: a filing at central reached by a person's read on the host, and a real task's start.
