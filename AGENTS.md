# Autoracer RC Repository Contract

## Product objective

Use the RC car to validate the shared autoracer localization, planning, control, and safety algorithms before those algorithms run on the real Hooke chassis. Preserve portability: Hooke uses CAN and the RC car uses serial, so transport and chassis differences belong behind explicit platform adapters and must not leak into Core.

## Source of truth

Only two long-lived branches are valid:

- `pilot-localization-sync-20260707` is the immutable CarMaker-validated baseline.
- `rc-platform-integration` is the only active integration branch and must remain a descendant of that baseline.

Do not revive `feature/official-autoware-launch`, `rc-car-migration`, or legacy Autoware composition patterns. Old repositories are reference material only: extract a proven algorithm or parameter when useful, then fit it to the current Core/platform boundaries.

## Machine roles

- The x86 workstation checkout at `/home/milesli/Desktop/RC/autoracer_hooke` is the primary development, review, mapping, and commit surface.
- The Orin checkout at `/home/wheeltec/Desktop/work/autoracer_hooke` is the future ARM deployment and hardware-validation surface. Do not use it until the x86 clean-build and CarMaker regression gates pass.
- Do not edit `rc-platform-integration` concurrently on both machines. Device-specific Orin edits use a short-lived remote branch and return through workstation review.
- Keep machine-specific Codex and MCP configuration under ignored `.codex/` directories. Shared context belongs in this file or tracked documentation.

## Architecture boundaries

- `src/core/` owns platform-independent sensing contracts, localization, fixed-course planning, trajectory generation, control, safety, and shared race composition.
- `src/platform/hooke2/` owns Hooke sensors, CAN transport, vehicle adaptation, and Hooke composition.
- `src/platform/rc/` owns RC sensors, serial transport, vehicle adaptation, RC geometry/parameters, and RC composition.
- Platform launch files may adapt device topics and parameters, but both platforms must feed the same Core topic and message contracts.
- Do not add a second Core orchestration or copy an Autoware launch stack into the RC platform.

## Assets and dependencies

- Course CSV files and their manifests are tracked under `courses/`.
- ROS bags, PCD maps, visualization results, and generated map products stay outside Git. On Orin the deployed map root is `/home/wheeltec/Desktop/work/rc-map-assets`.
- Resolve both platforms through `scripts/vendor/` and `dependencies/profiles/`. RC must use an explicit vendor workspace outside the product source tree; it must not own another resolver/import/build pipeline under `src/platform/rc/`.
- Never substitute a broad legacy `/home/wheeltec/autoware` underlay for the isolated RC vendor closure.
- The locked vendor import is currently blocked because `https://github.com/tier4/autoware_launch.x1.git` is unavailable and its pinned commit is not present in the public launcher repositories. Resolve that provenance problem explicitly before claiming a complete runtime build.

## Safety and verification

- Keep vehicle drive output disabled until the complete localization, planning, control, safety, device, and emergency-stop chain has been verified on the stationary RC car.
- A successful build or launch-file test is not a hardware validation. Record device presence, topics, transforms, localization convergence, trajectory publication, control gating, and actuator output separately.
- Do not test Hooke runtime behavior on the Orin RC environment. Protect the validated Hooke path with boundary tests instead.
- Generated `build/`, `install/`, and `log/` trees are disposable and must not be committed.

See `docs/design/repository-and-workspace-convergence.md` for the workspace model and `docs/rc_platform_contract.md` for the platform integration design.
