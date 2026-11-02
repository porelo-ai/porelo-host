# HO98 — A Project's Central Address Changed

**Status:** Idea.

**What must be true.** When the signed organization changes a project's central address, the host says so and does not
call the project carried. Today the follow takes `migrated` as lasting and compares no address: the old repository
stays on the host's forge, the published project file names the new one, which is absent, members' pushes find
nothing, and status still reads `carried`.

**Plan.** Keep the migrated address with the project's follow state and compare it at each follow. On a difference
either migrate the new repository at the next token and take the old one off once nothing on it is unpushed, as a
take-off does, or name the project as held until a person acts. Which one rests on whether a project keeps one
repository; it does for now. A test holds that the status never reads `carried` over an absent repository.
