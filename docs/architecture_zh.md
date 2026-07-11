# Ackermann Autoware 系统架构

用途：定义 RC/Hooke 平台接入同一套 Autoware 系统时的运行时边界、profile 装配规则、node/topic/dataflow、控制链路和算法替换边界。非用途：不描述仓库目录结构，不写现场操作步骤，不保留历史迁移说明。

## 系统边界

本仓库维护 Ackermann 车辆平台的 Autoware integration boundary。平台差异通过 vehicle profile、sensor-kit profile、calibration、sensing launch、vehicle adapter 和 operation runbook 表达；共享 autonomy 行为通过 official Autoware topic/message/frame/diagnostics contract 连接。

Core boundary:

```text
sensing profile
  -> localization
  -> mission planning
  -> behavior and motion planning
  -> official control
  -> command_gate
  -> platform vehicle adapter
  -> chassis
```

Rules:

- RC and Hooke are first-class platform targets.
- Platform-specific facts stay in profile packages and adapter packages.
- Shared planning/control behavior stays behind official Autoware contracts.
- Chassis transport differences stay below the vehicle adapter boundary.
- `src/external/autoware` is a pinned upstream dependency area; 不在 `src/external/autoware` 里做隐形修改.
- 自研 planning/control 候选 must be explicitly wired through the same contracts.

## Profile 装配

Autoware launch discovers platform packages by `vehicle_model` and `sensor_model`.

```bash
ros2 launch autoware_launch autoware.launch.xml \
  vehicle_model:=autoracer_rc \
  sensor_model:=autoracer_rc_sensor_kit
```

| Launch argument | Package naming contract | RC package | Responsibility |
| --- | --- | --- | --- |
| `vehicle_model:=autoracer_rc` | `$(vehicle_model)_description` | `autoracer_rc_description` | Vehicle geometry, vehicle info, vehicle URDF/xacro. |
| `vehicle_model:=autoracer_rc` | `$(vehicle_model)_launch` | `autoracer_rc_launch` | Vehicle interface launch, safety gate wiring, RViz profile. |
| `sensor_model:=autoracer_rc_sensor_kit` | `$(sensor_model)_description` | `autoracer_rc_sensor_kit_description` | Sensor-kit URDF/xacro and sensor extrinsics. |
| `sensor_model:=autoracer_rc_sensor_kit` | `$(sensor_model)_launch` | `autoracer_rc_sensor_kit_launch` | LiDAR/IMU drivers, filtering, sensing topics. |

Hooke uses the same contract:

```text
vehicle_model:=autoracer_hooke
sensor_model:=autoracer_hooke_sensor_kit
```

Operator scripts are thin entrypoints:

- `scripts/rc/` starts and stops RC runtime flows.
- `scripts/hooke/` fails fast while Hooke profile packages are guarded.
- `scripts/common/` contains shared helpers and must not encode vehicle facts.

## 平台状态

| Platform | Vehicle model | Sensor model | Runtime status | Source boundary |
| --- | --- | --- | --- | --- |
| RC Ackermann | `autoracer_rc` | `autoracer_rc_sensor_kit` | active platform profile | `src/autoracer_rc_*` |
| Hooke | `autoracer_hooke` | `autoracer_hooke_sensor_kit` | `disabled_placeholder` / not runtime ready | `src/autoracer_hooke_*` |

Platform runtime status is commit-scoped. A commit may have one runnable
platform, multiple runnable platforms, or no runnable platform while a shared
contract is under modification. Runtime scripts must make that state explicit
and must fail fast for non-runnable profiles.

Hooke profile placeholders remain guarded by `COLCON_IGNORE` until the vehicle
description, sensor-kit description, sensing launch, vehicle launch, adapter
wiring, and calibration facts are present as coherent profile packages.

Reference material for Hooke integration:

```text
src/hooke2_vehicle
src/hardware_drivers
src/wd_msgs
```

Reference material is not a runtime profile by itself. Runtime launch selection
must use official profile packages.

## Nodeviewer/Dataflow

Direct-open nodeviewer-style graph:

```text
docs/architecture/rc_official_runtime_graph.html
```

The HTML graph is a static architecture view with embedded SVG. It opens in a
browser without Mermaid, CDN access, or a separate rendering step. It describes
node/topic/dataflow relationships; it is not an on-car HMI and not a repository
layout document.

## Shared Autoware Stack

The shared stack boundary is the same for every platform profile:

```text
/sensing/lidar/raw/pointcloud
/sensing/lidar/concatenated/pointcloud
/sensing/imu/imu_data
/localization/pose_with_covariance
/localization/kinematic_state
/planning/mission_planning/route
/planning/trajectory
/control/command/control_cmd
/autoracer/control/safe_control_cmd
/vehicle/status/*
```

Control path:

```text
/planning/trajectory
  -> official Autoware control
  -> /control/command/control_cmd
  -> autoracer_safety/command_gate
  -> /autoracer/control/safe_control_cmd
  -> platform vehicle adapter
```

Adapter responsibilities:

- Consume `/autoracer/control/safe_control_cmd` as the adapter-facing command.
- Publish `/vehicle/status/velocity_status`, `/vehicle/status/steering_status`, `/vehicle/status/gear_status`, and `/vehicle/status/control_mode`.
- Convert `/vehicle/status/velocity_status` to `/sensing/vehicle_velocity_converter/twist_with_covariance` for official localization stopped-check and gyro odometer consumers.
- Preserve Autoware units and frame semantics.
- Keep CAN/UART/byte protocol details inside the adapter.

## Hooke Platform Path

```mermaid
flowchart LR
  subgraph H_Sensing["Hooke sensing / profile"]
    H_Lidar["Hesai/Pandar LiDAR\nnebula_hesai"]
    H_Fix["Fixposition\nGNSS/INS/IMU"]
    H_Map["Autoware map\nPCD + Lanelet2 + projector"]
  end

  subgraph H_Localization["Localization"]
    H_PC["/sensing/lidar/concatenated/pointcloud"]
    H_Filter["pointcloud_voxel_filter\n/sensing/lidar/filtered/pointcloud"]
    H_Seed["/sensing/gnss/pose_with_covariance\nor localization seed"]
    H_NDT["autoware_ndt_scan_matcher"]
    H_Pose["/localization/pose_with_covariance"]
    H_State["/localization/kinematic_state"]
  end

  subgraph Upper["Shared official Autoware upper stack"]
    Planner["official Autoware planning\nroute + behavior + motion"]
    Traj["/planning/trajectory"]
    Ctrl["official Autoware control"]
    Cmd["/control/command/control_cmd"]
    Gate["autoracer_safety\ncommand_gate"]
    Safe["/autoracer/control/safe_control_cmd"]
  end

  subgraph H_Chassis["Hooke vehicle adapter"]
    HookeIf["Hooke adapter"]
    CAN["SocketCAN can0\n500000 bps"]
    HookeChassis["Hooke chassis"]
    H_Status["/vehicle/status/*"]
  end

  H_Lidar --> H_PC --> H_Filter --> H_NDT
  H_Fix --> H_Seed --> H_NDT
  H_Map --> H_NDT
  H_NDT --> H_Pose --> Planner --> Traj --> Ctrl --> Cmd --> Gate --> Safe
  H_NDT --> H_State --> Planner
  H_State --> Ctrl
  Safe --> HookeIf --> CAN --> HookeChassis
  HookeChassis --> CAN --> HookeIf --> H_Status
  H_Status --> H_State
  H_Status --> Ctrl
```

## RC Platform Path

```mermaid
flowchart LR
  subgraph R_Sensing["RC sensing / profile"]
    R_Lidar["Leishen C32\nlslidar_driver"]
    R_C32Adapter["c32_pointcloud_adapter\nPointXYZIRC"]
    R_Imu["Hipnuc / N300 Pro\nimu_filter_madgwick"]
    R_SeedSrc["RViz / ROS /initialpose"]
    R_Adapi["official RViz adaptor\nAD API initialize"]
    R_Map["Autoware map\nPCD + Lanelet2 + projector"]
  end

  subgraph R_Localization["Localization"]
    R_PC["/sensing/lidar/concatenated/pointcloud"]
    R_RawPC["/sensing/lidar/raw/pointcloud"]
    R_Filter["pointcloud_voxel_filter\n/sensing/lidar/filtered/pointcloud"]
    R_ImuTopic["/sensing/imu/imu_data_raw\n/sensing/imu/imu_data"]
    R_Seed["pose_initializer\n/initialpose3d"]
    R_NDT["autoware_ndt_scan_matcher"]
    R_Pose["/localization/pose_with_covariance"]
    R_State["/localization/kinematic_state"]
  end

  subgraph Upper2["Shared official Autoware upper stack"]
    Planner2["official Autoware planning\nroute + behavior + motion"]
    Traj2["/planning/trajectory"]
    Ctrl2["official Autoware control"]
    Cmd2["/control/command/control_cmd"]
    Gate2["autoracer_safety\ncommand_gate"]
    Safe2["/autoracer/control/safe_control_cmd"]
  end

  subgraph R_Chassis["RC vehicle adapter"]
    Serial["rc_serial_interface"]
    UART["UART command frame"]
    STM32["STM32 firmware\nAckermann PWM"]
    R_Status["/vehicle/status/*"]
  end

  R_Lidar --> R_RawPC --> R_C32Adapter --> R_PC
  R_PC --> R_Filter
  R_PC --> R_NDT
  R_Imu --> R_ImuTopic
  R_ImuTopic -.-> R_NDT
  R_SeedSrc --> R_Adapi --> R_Seed --> R_NDT
  R_Map --> R_NDT
  R_NDT --> R_Pose --> Planner2 --> Traj2 --> Ctrl2 --> Cmd2 --> Gate2 --> Safe2
  R_NDT --> R_State --> Planner2
  R_State --> Ctrl2
  Safe2 --> Serial --> UART --> STM32
  STM32 --> Serial --> R_Status
  R_Status --> R_State
  R_Status --> Ctrl2
```

The `Shared official Autoware upper stack` section is the common contract. RC
and Hooke differences are limited to sensing/profile facts, seed sources,
calibration assets, map assets, and vehicle adapter transport.

## Algorithm Boundary

Default upper-stack behavior uses official Autoware planning/control.

```text
src/autoracer_planning
src/autoracer_control
```

These packages are 自研 planning/control 候选. They are valid extension points
only when wired explicitly through the same official input/output contracts.

Rules:

- Preserve message types, units, frames, and diagnostics contracts.
- Replace modules in launch/profile configuration, not in shell wrappers.
- Keep `autoracer_safety` between upstream control and chassis adapters.
- Keep platform-specific forks below profile or adapter boundaries.

## Runtime Acceptance Order

1. Sensing/TF: pointcloud, IMU, static TF, and vehicle status topics are present.
2. Localization: map assets load, seed pose is accepted, NDT pose and `kinematic_state` publish.
3. Planning: route/goal generates `/planning/trajectory`.
4. Control: official control publishes `/control/command/control_cmd`.
5. Gate: disabled mode outputs stop; enabled mode publishes `/autoracer/control/safe_control_cmd`.
6. Adapter: command direction, velocity sign, steering sign, gear/control mode, and timeout behavior are correct.
7. Low-speed drive: run with explicit speed limits, collect bag/log evidence, and update reference facts if calibration changes.
