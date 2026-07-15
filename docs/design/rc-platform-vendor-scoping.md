# ADR: RC-owned vendor dependency isolation

- Status: Superseded by shared vendor profiles
- Date: 2026-07-15
- Applies to: Historical RC-owned dependency metadata and tooling only

> This ADR is retained only to explain the rejected isolated-pipeline design. It
> must not be implemented. The active decision is documented in
> `docs/design/shared-vendor-profiles.md`: Hooke and RC use one resolver, importer,
> build path, and environment model, while profiles and independent materialized
> workspaces contain the platform differences.

## Context

Hooke2 already has a validated dependency import, build, and startup path. That
path is a frozen product baseline, not a path to refactor while adding RC support.
The same rule applies to `src/core`: RC reuses it unchanged through its published
ROS interfaces.

The repository-wide `dependencies/vendor-packages.tsv` is an existing two-column
inventory of 103 package-name/path records. The repository definitions and pinned
revisions remain in `dependencies/autoracer.repos` and
`dependencies/versions.lock.yaml`. Those files are read-only inputs to RC work.

The decision previously accepted in this ADR would have expanded the TSV with
scope and repository columns, added a global platform selector, and routed the
existing dependency scripts through that selector. That would put RC development
inside the already-validated Hooke2 dependency path and make an RC change capable
of changing Hooke2 defaults. That coupling is no longer acceptable.

RC still needs a reproducible dependency closure containing shared Autoware
packages and RC-specific LiDAR and IMU packages. It also needs executable import
and build verification without using Hooke2 as its regression harness.

## Superseded decision

The following parts of the earlier decision are superseded and must not be
implemented:

- changing `dependencies/vendor-packages.tsv` from two columns or adding scope
  metadata to it;
- adding `AUTORACER_PLATFORM`, a default platform, or another repository-global
  selector;
- modifying existing generic import, rosdep, vendor-build, product-build, or
  orchestration scripts to understand RC;
- selecting or rebuilding Hooke2 as proof that RC dependency work is correct;
- running core, Hooke2, CarMaker, startup, runtime, or hardware tests on the Orin
  as part of this work.

There is consequently no `hooke2`, `rc`, or `all` mode in shared dependency
tooling, and no unset-selector behavior to preserve or test.

## Decision

Add a narrow RC-owned dependency entry under `src/platform/rc/dependencies/`.
All new selection, import, rosdep, and build orchestration needed by RC stays
there. An equivalently clear RC-owned path is acceptable only if the
implementation documents why it is RC-only and the frozen-path guard proves it
cannot affect Hooke2.

### RC manifest contract

The RC-owned manifest is a metadata-only list of canonical package names. It does
not contain source URLs, Git revisions, copied package paths, launch files,
parameters, or orchestration. RC tooling resolves each name against the unchanged
two-column `dependencies/vendor-packages.tsv`, then resolves repository ownership
and revisions from the unchanged canonical repository and lock files.

The intended RC closure currently contains 82 canonical package names: the shared
packages RC consumes plus these four RC hardware packages:

```text
hipnuc_imu
hipnuc_lib_package
lslidar_driver
lslidar_msgs
```

`tier4_localization_launch` remains a shared dependency consumed by RC.
Hooke2-only drivers and `autoware_pure_pursuit` are not in the RC closure. Exact
membership and count are RC contract-test assertions; they do not reclassify or
rewrite the global inventory.

The resolver must reject duplicate names, unknown names, unsafe paths, ambiguous
repository ownership, missing revisions, disagreement between the repository and
lock files, and an empty closure before import or build work starts. Its output is
deterministic and preserves canonical package order.

### RC execution boundary

RC uses an explicitly RC-named workspace and RC-owned commands. It must not use or
mutate the established Hooke2 `vendor_ws`, call an existing generic dependency or
build script, or fall back to a Hooke source checkout. A failed RC resolution or
private-source fetch stops with a nonzero result; it never retries through the
Hooke2 path or expands to the full 103-package inventory.

The RC importer may create a filtered repository document in a temporary RC
workspace. That generated file references the canonical repository URLs and
revisions; it is not another revision authority. Only packages named by the RC
manifest are copied into the RC underlay, and verification rejects both missing
packages and stale extras.

RC-owned rosdep and build entry points may consume the frozen core as a prerequisite
of the RC target, but they target only the RC closure. They do not build or test a
Hooke2 target. Existing repository-level scripts remain byte-for-byte unchanged.

### Shared core and interfaces

Dependency isolation does not move or copy autonomy behavior. Localization,
planning, control, safety, command gating, and runtime management remain in the
unchanged `src/core`. RC adapters and bringup continue to consume its existing
normalized sensing, vehicle-status, and control-command interfaces.

RC contract tests may inspect RC code to assert that it uses those shared
interfaces. They must not execute a test located under `src/core` or modify core
to make an RC test pass. The only required core evidence is a Git path/diff audit
showing that no core file changed.

## Frozen boundary

The implementation baseline records a Git revision before RC dependency work.
Final path guards must show no change relative to that baseline in:

- `src/core/`;
- `src/platform/hooke2/`;
- existing repository-level scripts under `scripts/`;
- `dependencies/vendor-packages.tsv`;
- the canonical repository and revision files; and
- Hooke2 launch, parameter, manifest, dependency, build, runtime, hardware-test,
  and CarMaker paths.

These are audit targets only. The guard does not authorize executing code or tests
from a frozen path.

## Private-source access gate

The RC closure includes `tier4_localization_launch`, whose canonical source is the
private `autoware_launch.x1` repository. Access to that repository is currently
unavailable on the Orin. Full RC network import and executable build verification
are therefore **Blocked** until credentials can read the pinned canonical revision.

The blocker must remain explicit in reports. Source-only tests, fixture-backed
import tests, an already validated Hooke2 underlay, or successful access to public
repositories cannot be reported as a successful RC import or build. Credentials
must not be printed, and the RC path must not borrow the Hooke2 checkout to bypass
the gate.

## Verification matrix

| Verification | Permitted evidence | Current Orin status |
|---|---|---|
| Frozen core/Hooke2/shared scripts | Git path and diff guard only | Required |
| RC dependency resolver/import contracts | RC-owned unit tests with temporary fixtures and fake executables | May run |
| RC adapter/bringup contracts | Tests located under `src/platform/rc` only | May run |
| RC dependency import and RC build | RC-owned commands against the pinned RC closure | **Blocked** by private `autoware_launch.x1` access |
| Hooke2 build, tests, startup, or runtime | None; frozen baseline | Not run |
| CarMaker verification on Orin | None; outside this RC change | Not run |
| Live LiDAR presence, rate, frame, fields, or timestamps | Live RC bench evidence | **Not-tested** because LiDAR has not been started |
| Full RC sensing, vehicle, and race behavior | Live RC hardware evidence | **Not-tested** |

No source, unit, contract, import, or build result upgrades a live-hardware row.
There is no CarMaker acceptance activity on the Orin for this change.

## Consequences and tradeoff

The RC-owned manifest is a small, intentional duplication of dependency
*membership metadata*. That isolation is the mechanism that keeps RC development
from changing an already validated Hooke2 workflow. The list may reference shared
package names and canonical revisions, but it is not a duplicated autonomy stack:
it copies neither `src/core` nor Hooke2 launch, parameters, adapters, or
orchestration.

The cost is one RC-specific entry point and one membership list to maintain. The
benefit is a narrow review boundary: an RC dependency change can be tested and
built as RC work, while Hooke2 behavior and defaults remain untouched. A future
change to shared dependency tooling would require a separate ADR and independent
validation; it is not implied by this decision.
