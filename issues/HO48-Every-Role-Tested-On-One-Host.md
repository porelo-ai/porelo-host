# HO48 — Every Role Tested On One Host

**Status:** Review.
**Size:** L - the Molecule scenario rebuilt around the three roles, grown with each issue it tests.

**What must be true.** One throwaway VM runs a host admin, two project admins and a developer with two laptops in both
projects through every act and refusal of [HO42](README.md#ho42) to [HO47](README.md#ho47).

## Why

The scenario today brings one person's project up; every issue of the split changes what it must show.

## Plan

- Stand-ins for the laptops (ssh and WireGuard key pairs), the host admin's CA, two signed projects with access
  repositories, and a central forge.
- The acts in order: prepare ([HO42](README.md#ho42)), admit ([HO43](README.md#ho43)), register
  ([HO44](README.md#ho44)), bring and join ([HO45](README.md#ho45)), sync with the list changed twice
  ([HO46](README.md#ho46)), push ([HO47](README.md#ho47)), take off and `down`; each refusal seen red first.

## Acceptance

- The scenario green on the final tree, within the runner's job bounds.
