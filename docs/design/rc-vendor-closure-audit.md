# RC Vendor Closure Audit

- Date: 2026-07-15
- Development machine: x86 workstation
- Product commit under audit: `9696492`
- Status: Blocked on one fixed private source; candidate profile not yet locked

## Inputs

The product roots are `src/core` and `src/platform/rc`. Runtime/build dependencies
are read from their `package.xml` files; test dependencies are excluded. Transitive
dependencies are read from package manifests in repositories pinned by
`dependencies/autoracer.repos`.

Twelve of the thirteen RC candidate repositories were materialized at their fixed
commits in `/tmp/autoracer-dependency-audit/src`. Eleven completed through `vcs
import`; the large `autoware_universe` repository completed through a single-commit
shallow fetch of the same pinned SHA.

The remaining repository is:

```text
https://github.com/tier4/autoware_launch.x1.git
d9fa76bfb2201d6015c0544765d6bfa67430e7d2
autoware/launcher/tier4_universe_launch/tier4_localization_launch/package.xml
```

Unauthenticated access fails with `could not read Username for 'https://github.com'`.
No legacy workspace was used as a substitute.

## Current evidence

`scripts/vendor/derive_profile.py` fails closed when the selected package manifest
is unavailable. It therefore does not emit a supposedly complete RC profile with
the real inputs.

For diagnosis only, the missing launcher package was temporarily represented in
`/tmp` as a leaf with no dependencies. That produces a 77-package lower bound.
The existing 82-package candidate contains every lower-bound package plus:

```text
autoware_pcl_extensions
autoware_pointcloud_preprocessor
autoware_pose_covariance_modifier
autoware_sensing_msgs
managed_transform_buffer
```

Those five packages must not be removed yet: any may be introduced by the real
`tier4_localization_launch/package.xml`. The temporary leaf was deleted after the
comparison and was never copied into the product repository or vendor profile.

## Completion action

Obtain the exact package directory from the pinned private commit through an
authorized Git remote, controlled mirror, or provenance-recorded source archive.
Place it at the catalog path in a temporary fixed-source tree and rerun:

```bash
python3 scripts/vendor/derive_profile.py \
  --source-root /path/to/fixed-sources \
  --product-root src/core \
  --product-root src/platform/rc
```

Only an exit-zero result from the real manifest may replace
`dependencies/profiles/rc.packages`. The regenerated list must then pass resolver,
clean import, vendor build, and product build verification.
