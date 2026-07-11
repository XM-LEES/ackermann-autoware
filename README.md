# Ackermann Autoware

Autoware integration workspace for Ackermann vehicle platforms.

This repository maintains platform profiles, sensor-kit profiles, chassis
adapters, safety boundaries, runtime scripts, mapping workflow, and interface
documentation for RC and Hooke vehicles. RC and Hooke are first-class platform
targets. Shared autonomy behavior stays behind official Autoware topic,
message, frame, parameter, and diagnostics contracts; platform-specific facts
belong in profiles and adapters.

## Platform Targets

| Platform | Vehicle profile | Sensor-kit profile | Status |
| --- | --- | --- | --- |
| RC Ackermann | `autoracer_rc` | `autoracer_rc_sensor_kit` | Active platform profile. |
| Hooke | `autoracer_hooke` | `autoracer_hooke_sensor_kit` | Integration pending; placeholders are guarded by `COLCON_IGNORE`. |

Platform status is versioned per commit. A repository revision may support one
platform at runtime, multiple platforms at runtime, or no platform at runtime
while shared interfaces are being changed. The status table is the coordination
surface for that state; it describes current integration readiness without
changing the long-term target list.

Current revision status:

- RC: active runtime profile and primary development path.
- Hooke: profile integration pending; no runtime-ready profile is exposed.

Top-level composition uses the official Autoware launch path.
Official profile composition example:

```text
vehicle_model:=autoracer_rc
sensor_model:=autoracer_rc_sensor_kit
```

The RC operator wrappers under `scripts/rc/` call the same official launch path
and add field checks, runtime defaults, and controlled shutdown.

On-car runtime entrypoint commands are maintained under [RC
Startup](#rc-startup) and in the RC runbook.

## Runtime Architecture

```text
Map -> Localization -> Planning -> Control
Sensing -> Localization
Sensing -> Perception (available_disabled) -> Planning
Control -> VehicleCmdGate -> Project Safety Gate -> Vehicle Adapter -> Chassis
/vehicle/status/* -> Localization / Control
```

RC currently launches Map, Sensing, Localization, Planning, Control, Vehicle,
AD API, and System/Diagnostics. Perception retains the official integration
boundary but is disabled by default. The canonical data flow and module
responsibilities are in `docs/architecture_zh.md`.

## Repository Layout

```text
autoracer.repos             Dependency manifest for selected external packages.
defaults.env                Runtime defaults shared by operator wrappers.
config/middleware/          Versioned middleware configuration for onboard runtime.
docs/                       Current architecture, development, operation, and reference docs.
docs/architecture/          Direct-open node/topic/dataflow architecture views.
maps/                       Local map directory placeholder.
scripts/                    Import, build, run, and smoke-test helpers.
scripts/common/             Shared helper boundary; no vehicle-specific facts.
scripts/rc/                 RC operator entrypoints.
scripts/hooke/              Hooke handoff entrypoints; fail fast until the profile is enabled.
tools/mapping/              Versioned x86 bag inspection, Super-LIO, and map preparation tools.
tools/system/               Reproducible onboard host-service provisioning.
src/external/autoware       Pinned upstream Autoware packages; keep patches explicit.
src/autoracer_rc_*          RC vehicle and sensor-kit profiles.
src/autoracer_hooke_*       Hooke vehicle and sensor-kit profile placeholders.
src/autoracer_description   Legacy/reference description and static TF assets.
src/autoracer_sensing       Small sensor adapters used by platform profiles.
src/autoracer_safety        Final command gate before chassis adapters.
src/autoracer_vehicle_interface
                             Chassis adapters and vehicle status bridges.
src/autoracer_localization  Candidate localization helpers; not in the default runtime.
src/autoracer_planning      Candidate planning algorithms; not in the default runtime.
src/autoracer_control       Candidate control algorithms; not in the default runtime.
src/hardware_drivers        Vendored SocketCAN driver material used by Hooke integration.
src/hooke2_vehicle          Vendored Hooke vehicle reference material.
src/wd_msgs                 Vendored Hooke chassis messages and byte helpers.
```

## Documentation

| Document | Scope |
| --- | --- |
| [Platform development contract](docs/development_guide_zh.md) | Profile, package, adapter, algorithm, and upstream maintenance rules. |
| [System architecture](docs/architecture_zh.md) | Runtime modules, data flow, and platform boundaries. |
| [Interactive architecture browser](docs/architecture/project_architecture.html) | Direct-open offline visual projection of the system architecture. |
| [RC runbook](docs/operations/rc_runbook_zh.md) | On-car startup, shutdown, and validation flow. |
| [Mapping workflow](docs/operations/mapping_workflow_zh.md) | Bag capture, Super-LIO, map packaging, and synchronization. |
| [Interfaces and calibration](docs/reference/interfaces_and_calibration_zh.md) | Topic, frame, adapter, hardware, and calibration facts. |

Documentation responsibilities:

| Scope | Owner document |
| --- | --- |
| Repository purpose, target platforms, package layout | `README.md` |
| Platform development rules and package responsibilities | `docs/development_guide_zh.md` |
| Runtime Autoware system boundaries and data flow | `docs/architecture_zh.md` |
| On-car commands and field procedure | `docs/operations/*.md` |
| Topic, frame, parameter, and calibration facts | `docs/reference/interfaces_and_calibration_zh.md` |

## Build

The build scripts assume Ubuntu 22.04 with ROS 2 Humble installed at
`/opt/ros/humble`. Install the repository tooling before importing sources:

```bash
sudo apt install -y \
  python3-vcstool \
  python3-rosdep \
  python3-colcon-common-extensions \
  ros-humble-rmw-cyclonedds-cpp
```

Initialize rosdep once on a fresh host:

```bash
test -r /etc/ros/rosdep/sources.list.d/20-default.list || sudo rosdep init
```

Desktop/RViz plugin dependencies on a fresh ROS 2 Humble host:

```bash
sudo apt install -y \
  libpng++-dev \
  libpng-dev \
  nlohmann-json3-dev \
  qtbase5-dev \
  ros-humble-autoware-motion-utils \
  ros-humble-foxglove-bridge \
  ros-humble-rviz-2d-overlay-msgs \
  ros-humble-rviz-2d-overlay-plugins \
  ros-humble-xacro \
  libprotobuf-dev \
  protobuf-compiler \
  libpcap-dev
```

The selected upstream source snapshots are tracked under `src/external`; a
normal checkout must not run `vcs import` into that directory. Resolve system
dependencies and build the active runtime workspace:

```bash
cd <repo>
./scripts/install_rosdeps.sh
./scripts/build_minimal.sh
source ./scripts/ros_env.sh
```

On resource-constrained onboard compute:

```bash
COLCON_PARALLEL_WORKERS=1 MAKEFLAGS="-j2 -l2" ./scripts/build_minimal.sh
```

Candidate local algorithms and platform-reference packages are excluded by
default. Maintainers can compile them explicitly with `BUILD_CANDIDATES=true`
or `BUILD_REFERENCES=true`; neither option changes the active runtime graph.

After the onboard workspace is built, apply the Autoware DDS kernel settings,
CycloneDDS prerequisites, and privileged system-monitor reader:

```bash
sudo -E ./tools/system/configure_onboard_host.sh
```

## Runtime Contract

The platform side must preserve these shared Autoware surfaces:

```text
/sensing/lidar/concatenated/pointcloud
/sensing/imu/imu_data
/localization/pose_with_covariance
/localization/kinematic_state
/planning/trajectory
/control/command/control_cmd
/autoracer/control/safe_control_cmd
/vehicle/status/*
```

Chassis adapters must consume gated control commands, publish official vehicle
status topics, and keep raw transport details inside the adapter boundary.

Runtime host IPs, SSH credentials, and machine-local serial device names are not
architecture facts. Pass them through environment variables such as `MAP_PATH`,
`SERIAL_PORT`, `IMU_SERIAL_PORT`, and the `LIDAR_*` settings.

## RC Startup

Copy-paste operator commands are maintained in
`docs/operations/rc_runbook_zh.md`. Use that runbook as the source of truth for
localization-only, full-chain dry-run, and low-speed drive-enabled startup.

Minimal full-chain dry-run entry point:

```bash
MAP_PATH=/path/to/autoware_map \
SERIAL_PORT=/dev/ttyCH343USB0 \
ENABLE_DRIVE_COMMANDS=false \
./scripts/rc/rc_start_autoware.sh
```

Drive-enabled startup and autonomous-mode engagement are safety-critical field
operations. Follow the ordered checks and copy-paste commands in the RC runbook
instead of enabling drive from this overview.

Stop the runtime started by the formal RC wrappers:

```bash
./scripts/rc/rc_stop.sh
```

The stop command uses the runtime identity recorded under
`/tmp/autoracer_rc`; it does not scan for generic ROS process names and does not
stop an independently launched Foxglove Bridge.

## Safety Default

`ENABLE_DRIVE_COMMANDS=false` is the default. In this mode the official
Autoware planning/control chain may run, but the safety gate publishes stop
commands to `/autoracer/control/safe_control_cmd`. Set it to true only during a
controlled low-speed validation run.
