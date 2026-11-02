"""Record isolated organization commands without running services or changing real accounts."""

import json
import os
import subprocess
from pathlib import Path


def revoke(state, login="bob"):
    """Remove a person's memberships through the organization and run the real follow."""
    for project in state.reply["projects"]:
        project["members"] = [member for member in project["members"] if member["login"] != login]
    return state.host.execute(["org", "follow"], b"")


class FollowCommands:
    """A command stand-in whose replies are supplied independently of the host's access decisions."""

    def __init__(self, host, reply, record, runner):
        self.host, self.reply, self.record, self.runner = host, reply, record, runner
        self.exit, self.stderr, self.add_exit = 0, "", 0
        self.acls, self.added, self.pins, self.fetches = {}, [], [], []
        self.signers = {}

    def __call__(self, args, input=None):
        if args[0] == "systemd-run" and "org" in args:
            self.record(args, input)
            assert all(option in args for option in ("--pipe", "--wait", "--quiet", "--collect"))
            assert "DynamicUser=yes" in args and "ProtectHome=yes" in args
            words = args[args.index("porelo") + 1 :]
            assert words[:1] == ["org"] and "--json" in words
            if words[1] == "add-read-key":
                assert "PrivateNetwork=yes" not in args
                self.added.append(input)
                return subprocess.CompletedProcess(
                    args, self.add_exit, json.dumps({"revision": None, "added": True}), ""
                )
            if words[1] == "fetch":
                assert "PrivateNetwork=yes" not in args
                assert words[words.index("--host") + 1] == "host"
                for flag in ("--settings", "--ssh-key", "--known-hosts", "--pin"):
                    name = words[words.index(flag) + 1].rsplit("/", 1)[-1]
                    assert any(arg.startswith("LoadCredential=" + name + ":") for arg in args)
                self.pins.append(self.host.path("/etc/porelo-host/organization/pin").read_text())
                self.fetches.append(args)
                return subprocess.CompletedProcess(args, self.exit, json.dumps(self.reply), self.stderr)
            assert words[1] == "signers" and "PrivateNetwork=yes" in args
            loaded = next(arg.split(":", 1)[1] for arg in args if arg.startswith("LoadCredential=state:"))
            taken = json.loads(Path(loaded).read_text())
            assert {key: value for key, value in taken.items() if key != "projects"} == {
                key: value for key, value in self.reply.items() if key != "projects"
            }
            assert all(project in self.reply["projects"] for project in taken["projects"])
            project = words[words.index("--project") + 1]
            return subprocess.CompletedProcess(
                args,
                0,
                json.dumps({"project": project, "revision": self.reply["revision"], **self.signers[project]}),
                "",
            )
        if args[0] == "setfacl":
            assert args[1] == "--modify"
            self.record(args, input)
            self.acls[os.stat(args[-1]).st_ino] = {int(entry.split(":")[1]) for entry in args[2].split(",")}
            return subprocess.CompletedProcess(args, 0, "", "")
        return self.runner(args, input=input)


def prepare_follow(host, reply, record, runner, signers):
    """Install only fixture credentials and external command replies in the isolated root."""
    host.path("/etc/porelo-host/forge").mkdir(mode=0o755, parents=True, exist_ok=True)
    directory = host.path("/etc/porelo-host/organization")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    for name in (
        "organization.yml",
        "known_hosts",
        "read/organization",
        "read/organization.pub",
        "read/organization.added",
    ):
        path = directory / name
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.write_text("opaque\n")
        path.chmod(0o600)
    pin = directory / "pin"
    pin.write_text("".join(f'{admin["login"]} {admin["key"]}\n' for admin in reply["admins"]))
    pin.chmod(0o600)
    (directory / "applied.json").unlink(missing_ok=True)
    host.commands.update({"ssh-keygen", "setfacl", "userdel", "useradd", "groupadd", "systemd-run"})
    state = FollowCommands(host, reply, record, runner)
    state.signers = signers
    return state
