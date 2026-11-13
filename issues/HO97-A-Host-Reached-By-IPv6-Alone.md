# HO97 — A Host Reached By IPv6 Alone

```json
{
  "$schema": "issue-1.json",
  "id": "HO97",
  "title": "A Host Reached By IPv6 Alone",
  "state": "Idea",
  "size": "-",
  "priority": "Low",
  "rank": 13,
  "blockedBy": [],
  "covers": "A server reached by IPv6 alone is prepared: its public interface told by the IPv6 default route, the firewall and the forge holding for it."
}
```

**What must be true.** A server with no IPv4 default route, reached by IPv6 alone, is prepared like any other: the
base role tells its public interface by the IPv6 default route where no IPv4 one exists, and the firewall, the
forge's loopback and the runner's network hold for it as they hold for IPv4. Today `roles/base/tasks/host.yml` stops
such a server before anything is installed.
