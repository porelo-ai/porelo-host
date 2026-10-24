# HO23 — A Machine Rented And Given Back By OpenTofu

**Status:** Idea.

**What must be true.** An administrator rents a machine at a provider and gives it back by one OpenTofu module per
provider, whose state is kept encrypted with the administrator, so that Porelo's hosts can be had from more than one
provider and from a company's own tooling, outside the interface.

## Why

- Renting and giving back a host is today `porelo-host`'s, a Dart package of porelo-frontend, for Scaleway alone.
- porelo-project [PJ40](https://github.com/porelo-ai/porelo-project/blob/main/issues/README.md#pj40) names OpenTofu as
  the planned extension "for Porelo as a product for others", likelier than an adapter per provider in each language,
  and it runs on Linux, macOS and Windows.
- Setting a machine up and taking it down are the `host-admin` role's (porelo-project
  [PJ71](https://github.com/porelo-ai/porelo-project/blob/main/issues/README.md#pj71)), and may happen entirely outside
  Porelo; a module the administrator runs keeps them there, beside this repository's collection that sets the host up
  once it is rented.
