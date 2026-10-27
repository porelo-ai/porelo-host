# HO16 — The Person's Drive On OneDrive

**Status:** Idea.

**What must be true.** A project can choose OneDrive in place of Tresorit for the person's drive, and the `drive`
role then gives the host the same promise it gives with Tresorit: one folder, read and written, on a filesystem
nothing runs from, its login the person's at the stop, and `down` keeping the host while anything written is not
synced. Many companies keep their files there.

## To be checked, nothing decided

- **The client on the host.** Microsoft ships no OneDrive client for Linux. The candidates are `rclone` (its
  `onedrive` backend, as a sync or a mount) and `abraunegg/onedrive`. For each: how it is pinned and checked before it
  runs, as Tresorit's installer is checked against its signing CA, and what proves the download is the project's own;
  whether it syncs one folder two ways into `drive_path`; and how it says "fully synced", for `down`'s wait.
- **The client from the distribution's archive.** `rclone` and `onedrive` (abraunegg) are packaged in Ubuntu and
  Fedora, so apt or dnf installs them signed by the distribution, which answers "what proves the download" as it does
  for `ansible-core`. Weighed against the packaged version's age, since Microsoft's API changes.
- **GNOME Online Accounts' Microsoft 365** (msgraph through gvfs, GNOME 46 and later): it needs a desktop session,
  D-Bus and gvfs, and mounts files on demand rather than syncing a folder, so it has no "fully synced" for `down`'s
  wait. Whether any of it serves a headless host; likely not, with the reason read.
- **The login.** Microsoft's OAuth device flow fits the stop, since no password is typed on the host. A work account
  may need its tenant admin's consent for the client's app id. Where the refresh token lives on the host, readable by
  whom, and that `down` revokes it or at least removes it.
- **Encryption.** Tresorit encrypts end to end; OneDrive does not, so what lies on it is readable at Microsoft and by
  the company's admins. Once [HO37](README.md#ho37) gives the host every secret on standard input from the person's
  `secrets.kdbx` and [HO36](README.md#ho36) uploads its other files, the host's setup reads nothing from the drive, and
  an age-encrypted `wireguard.key.age` is not needed. Once [HO38](README.md#ho38) makes the drive the person's own, it
  holds only their own files. `secrets.kdbx` itself may lie on OneDrive, since only its master password opens
  it, which then carries the whole weight; the host never reads it. What stays open is the person's own files on a
  private drive, which are theirs to choose for.
- **Personal or business.** OneDrive personal, or OneDrive for Business and SharePoint libraries: which comes first.
- **The choice.** How the inventory names the drive's kind, beside `porelo_host_tresor`, so the role picks its
  client; porelo-frontend's matching issue, "OneDrive As The Project's Drive", asks the person for it and gives
  the login at the stop.
