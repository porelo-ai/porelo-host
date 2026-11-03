# HO110 — A Server Follows The Organization Admins' Keys

**Status:** Accepted.

**What must be true.** A server's pin holds the keys of the organization's Organization Admins beside its own Machine
Admins, so a Machine Admin changed or replaced by an Organization Admin takes effect on a running server at its next
follow, with no confirmation by the former admin, who may be gone. Taking that list needs no person on the server, and
it makes no account for anyone on it. A Machine Admin names no further Machine Admin; that is the Organization Admin's alone,
so a list a Machine Admin alone has changed is not taken. One stolen key of this role reaches every server; that is known and decided.

## To be checked

- **The new list:** `org fetch` answers the role's keys beside `admins`. `write_follow_pin` writes today's one list to
  both the pin and root's key file; it comes apart into two. The memberships keep reading `admins` alone, so the role
  gets no account, and its logins need not be among the state's `persons`, which `admins` must be. `admins[0]` still
  names the forge's account owner.
- **Root, decided:** the pin holds and follows the role's keys; root stays with the listed Machine Admins, so root's key
  file reads `admins` alone. An Organization Admin who needs root lists themselves as that machine's Machine Admin, a
  visible signed change, one server at a time. A stolen key of this role can do the same, visibly; that cost is accepted.
- **A server already set up:** its pin holds only its Machine Admins, so a commit the role signs is signed by no key it
  holds and is refused. It takes the list once, by one of those admins signing it, or by root's `org renew-pin`, whose
  input then carries both lists. Which of them, and what becomes of a server whose admin has gone, is to be read
  together with Porelo's judging of the pin.
- **How a server first takes it:** a server set up later gets the role's keys in the machine file `up` reads for its
  first pin, and the host's refusal of a pin with no key stays.
- **A server with no Machine Admin left:** today a state with empty `admins` is refused; whether an Organization Admin
  may leave a server so, and with what root's key file then holds.
- **A helper older than the fetch:** an older follow writes the pin from `admins` alone, and the next fetch judges by it.
  In what order a package and the collection may arrive, and that neither reads the other's list wrongly.
- **A follow that cannot fetch** keeps the old list, so a dismissed admin keeps root for as long as that lasts.
