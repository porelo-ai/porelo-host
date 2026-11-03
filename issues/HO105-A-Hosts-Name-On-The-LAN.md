# HO105 — A Host's Name On The LAN

**Status:** Idea.

**What must be true.** A person who gives their host by its `.local` name on a LAN either reaches it by that name after
`up`, or is told plainly that the name will not answer and what to use instead. Today the name stops resolving from any
other machine once `up` has put its firewall in place, with nothing that says so.

## Why

Measured on an Ubuntu 26.04 host after `up`: `avahi-daemon` is active and listening on UDP 5353, and the name answers on
the host itself. The firewall in `roles/base/templates/firewall.nft.j2` ends in `drop` on every interface holding a
default route and allows only TCP 22, so 5353 is dropped there. Three mDNS queries from a neighbor reached the host's
interface by `tcpdump`, no answer left it, and `getent` on the neighbor found nothing. The same queries against avahi on a
machine without this firewall got three answers of three. The rule was not lifted on the host to compare. The collection
names no avahi, mDNS or 5353 anywhere, so this follows from the port 22 policy and was never decided.

## Acceptance

- From a second machine on the same LAN, after `up`, the name does what the chosen answer says; with the name
  unanswered, whatever offers it says so.
- A host on a public interface answers no mDNS from outside its link, measured by a query from another network.

## Open questions

- Should `up` allow mDNS, on request for a LAN host and never by default on a rented server, since the firewall's
  promise is port 22 alone? Or does the host stay closed, with the name given up in favor of an address or a name entry?

## To be checked

- Whether the name answers before `up` on a host from the same image, and where its avahi comes from: the collection does
  not install it.
- IPv6 mDNS, which was not measured.
