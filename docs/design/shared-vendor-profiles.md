# ADR: One vendor mechanism with platform profiles

- Status: Accepted
- Date: 2026-07-15
- Applies to: third-party dependency resolution, import, build and environment setup

## Decision

Hooke and RC use one dependency mechanism under `scripts/vendor/` and the existing
top-level compatibility entry points. Platform differences are declarations under
`dependencies/profiles/` plus separate materialized workspaces.

`dependencies/autoracer.repos` is the only authority for repository URL and fixed
revision. `dependencies/vendor-packages.tsv` lists every package that may be
selected. A profile selects package names; the resolver derives the owning
repositories and produces deterministic import/build input.

The default profile is `hooke2` and must continue to resolve the CarMaker-validated
99 packages from 14 repositories. RC must be selected explicitly and must provide
an external `AUTORACER_VENDOR_WS`; it cannot overwrite Hooke `vendor_ws`.

The RC profile currently remains a candidate until its closure can be regenerated
from all fixed-revision `package.xml` files. The only unavailable input at the time
of this decision is private `autoware_launch.x1` package
`tier4_localization_launch`. A hard-coded count is not acceptance evidence.

## Rejected alternatives

- A complete resolver/import/build implementation under `src/platform/rc/` was
  rejected because it duplicates policy and allows Hooke and RC behavior to drift.
- Importing all catalog repositories for every platform was rejected because RC
  hardware sources would change the Hooke network path.
- Committing `vendor_ws/src` was rejected because fixed sources can be materialized
  from the catalog; inaccessible private provenance must be solved explicitly,
  not hidden in a copied workspace.

## Invariants

- Dependency profiles never move autonomy logic out of `src/core/`.
- Fixposition, GNSS, CAN and Nebula enter RC only if the actual product dependency
  graph reaches them; there is no Hooke-to-RC package mapping.
- `vendor_ws`, `build`, `install` and `log` remain ignored generated state.
- Orin work starts only after x86 clean builds and the CarMaker Hooke regression.
