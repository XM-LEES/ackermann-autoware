# scripts/common

This is the shared helper layer for operator scripts.

Rules:

- Shared helpers may validate common Autoware runtime inputs.
- Shared helpers must not encode RC or Hooke hardware facts.
- Vehicle-specific commands stay in `scripts/rc/` or `scripts/hooke/`.
- Hardware facts belong in official vehicle/sensor profiles or runtime
  environment variables, not in this common layer.

Current state:

- `scripts/rc/` is the active runtime operator surface for the RC car.
- `scripts/hooke/` is a pending handoff surface until the real Hooke official
  profiles are complete.
- Existing root helpers such as `scripts/run_official_autoware.sh` and
  `scripts/ros_env.sh` implement shared runtime behavior used by the RC operator
  surface. Move logic here only when it is genuinely shared and not hardware
  specific.
