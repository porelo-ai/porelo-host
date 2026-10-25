# HO22 — Ssh Reached Only Through The VPN Once It Is Up

**Status:** Accepted.

**What must be true.** Once `up` has brought the VPN up, the host's ssh answers only on the VPN's address; its public
address offers the VPN's UDP port alone. Before that, ssh on the public address is the one way in, since `up` needs it
until the host's WireGuard key, which lies on the person's drive, is read at the stop. A person whose VPN fails still
gets back onto the host by a way that is written down and tried.

## Why

`roles/vpn`'s firewall (`templates/firewall.nft.j2`) keeps `vpn_ssh_port`, 22/tcp by default, open on the public
interfaces after `up`, beside the VPN's port. So the host's ssh stays reachable from anywhere for as long as the host
runs, though everything else it offers is reached only through the VPN. Every login attempt from the internet meets
it, and a flaw in `sshd` is open to all, not only to the person's VPN.

## Open questions

- **When does the public ssh close:** at the end of `up`, once the VPN is seen to carry ssh, or only after the person
  has connected through it once?
- **How does `porelo-host` reach the host afterwards** for a second `up`, for `down` and for the stop's terminal: over
  the VPN, which then must be up on the person's computer for every one of them?
- **How does a person get back in when the VPN fails:** the provider's console, a rescue system the provider boots,
  a second key, or a public ssh that `down` or the provider's API opens again for a while? Which of these is offered,
  and who tries it?
- **What of the Molecule scenario,** which reaches the test VM on its public address today: does the test bring up a
  VPN peer of its own, or keep the public ssh by a setting only the test sets?
