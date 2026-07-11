# 接口、Topic 与标定事实

本文集中维护跨模块接口、平台硬件事实、frame 和标定值。它不包含启动步骤，也不把参考代码描述成当前运行能力。

## 状态定义

| 状态 | 本文含义 |
| --- | --- |
| `active` | 当前 profile 使用并需要保持兼容的事实。 |
| `reference` | 来自旧实现或供应方代码，仅用于设计和核对。 |
| `pending` | 目标接口已经定义，尚未完成平台集成或实车验证。 |

接口状态随 commit 维护。硬件、外参或协议发生变化时，必须同时更新 profile、adapter、测试和本文对应事实。

## Shared Topic 契约

| Topic | 类型 | 生产者 | 消费者 | 语义 |
| --- | --- | --- | --- | --- |
| `/sensing/lidar/raw/pointcloud` | `sensor_msgs/msg/PointCloud2` | platform LiDAR driver | sensor adapter、建图工具 | 驱动原始字段布局。 |
| `/sensing/lidar/concatenated/pointcloud` | `sensor_msgs/msg/PointCloud2` | platform sensor adapter/concatenator | official localization、可选 perception | Autoware 标准点云输入。 |
| `/sensing/lidar/filtered/pointcloud` | `sensor_msgs/msg/PointCloud2` | project voxel filter | 诊断、远程显示、建图辅助 | 非默认 NDT 输入。 |
| `/sensing/imu/imu_data_raw` | `sensor_msgs/msg/Imu` | platform IMU driver | IMU filter、录包 | 驱动原始 IMU。 |
| `/sensing/imu/imu_data` | `sensor_msgs/msg/Imu` | IMU filter | Gyro Odometer、control utilities | 经过 orientation/filter 处理的 official IMU 输入。 |
| `/initialpose` | `geometry_msgs/msg/PoseWithCovarianceStamped` | RViz 2D Pose Estimate / operator client | official RViz adaptor | 人工初始位姿操作入口。 |
| `/api/localization/initialize` | `autoware_adapi_v1_msgs/srv/InitializeLocalization` | official RViz adaptor / AD API client | pose initializer | 官方定位初始化 API。 |
| `/initialpose3d` | `geometry_msgs/msg/PoseWithCovarianceStamped` | pose initializer | EKF/localization reset | official localization 内部初始化入口。 |
| `/localization/pose_estimator/pose_with_covariance` | `geometry_msgs/msg/PoseWithCovarianceStamped` | NDT Scan Matcher | EKF Localizer | pose estimator 输出。 |
| `/localization/pose_with_covariance` | `geometry_msgs/msg/PoseWithCovarianceStamped` | EKF Localizer | planning、control、safety/diagnostics | 融合后的 map-frame pose。 |
| `/localization/kinematic_state` | `nav_msgs/msg/Odometry` | EKF Localizer + Stop Filter | planning、control、diagnostics | 最终车辆运动状态；NDT 不直接产生该 topic。 |
| `/planning/trajectory` | `autoware_planning_msgs/msg/Trajectory` | official Autoware planning | official Autoware control | 路径、速度和时序轨迹。 |
| `/control/command/control_cmd` | `autoware_control_msgs/msg/Control` | official VehicleCmdGate | project `command_gate` | 官方 command arbitration 后的控制命令。 |
| `/autoracer/control/safe_control_cmd` | `autoware_control_msgs/msg/Control` | project `command_gate` | platform vehicle adapter | 底盘侧 gated control；禁用或超时为 stop。 |
| `/vehicle/status/velocity_status` | `autoware_vehicle_msgs/msg/VelocityReport` | platform vehicle adapter | localization、control、diagnostics | 纵向速度和 yaw rate。 |
| `/sensing/vehicle_velocity_converter/twist_with_covariance` | `geometry_msgs/msg/TwistWithCovarianceStamped` | vehicle velocity converter | pose initializer、Gyro Odometer | stopped-check 和 twist estimator 输入。 |
| `/vehicle/status/steering_status` | `autoware_vehicle_msgs/msg/SteeringReport` | platform vehicle adapter | control、diagnostics | 前轮转角反馈。 |
| `/vehicle/status/gear_status` | `autoware_vehicle_msgs/msg/GearReport` | platform vehicle adapter | VehicleCmdGate、diagnostics | 实际挡位反馈。 |
| `/vehicle/status/control_mode` | `autoware_vehicle_msgs/msg/ControlModeReport` | platform vehicle adapter | operation mode、diagnostics | 底盘控制模式反馈。 |

上层模块只依赖 shared topic，不依赖 UART/CAN 私有消息。支持命令如 gear、turn indicators、hazard lights 和 emergency 保持 official `/control/command/*` contract，由目标平台 adapter 按硬件能力实现。

## RC Active Facts

RC vehicle profile 与 sensor-kit profile 当前为 `active`。以下内容是当前实现事实，现场操作命令以 `docs/operations/rc_runbook_zh.md` 为准。

### LiDAR

Leishen C32 配置位于：

```text
src/autoracer_rc_sensor_kit_launch/config/lslidar_cx.yaml
```

网络与 driver contract：

| 项目 | 值 |
| --- | --- |
| LiDAR device endpoint | `192.168.1.200` |
| Orin LiDAR-facing source address | `192.168.1.102/32` |
| MSOP / DIFOP | `2368` / `2369` |
| Pointcloud frame | `lidar_top` |
| Driver output | `/sensing/lidar/raw/pointcloud` |
| Autoware adapter output | `/sensing/lidar/concatenated/pointcloud` |

专用 host route 只连接 `192.168.1.200/32`，避免 LiDAR 网口接管 WiFi/LAN 默认路由。`192.168.1.102` 是 Orin 在 LiDAR-facing link 上的 host source address，不是一次额外转发。

C32 raw 字段保留建图所需的 ring/time 信息。`c32_pointcloud_adapter` 将 raw 布局转换为 Autoware `PointXYZIRC`，发布 concatenated topic。当前 official localization 默认消费 `/sensing/lidar/concatenated/pointcloud`。`/sensing/lidar/filtered/pointcloud` 使用 profile 中可配置的体素和点数限制，仅供诊断、Foxglove 与建图辅助，默认不替代 NDT 输入。

### IMU 与外参

RC IMU driver 发布 `/sensing/imu/imu_data_raw`，Madgwick filter 发布 `/sensing/imu/imu_data`。当前运行外参唯一来源：

```text
src/autoracer_rc_sensor_kit_description/config/sensor_kit_calibration.yaml
```

现有值来自车体静止标定：IMU 约 `100 Hz`，静止加速度标准差低于 `0.007 m/s^2`；C32 近场地面拟合残差约 `0.01 m`。配置包含物理安装倾角和约 `-90 deg` 的 LiDAR yaw，不把 `base_link -> imu_link` 或 `base_link -> lidar_top` 假设为零姿态。

Super-LIO 相对外参位于：

```text
tools/mapping/config/rc_c32_super_lio.yaml
```

固定版本 Super-LIO 按 Eigen column-major 读取扁平旋转数组。该文件必须由 sensor profile 的相对变换核对，不能按常见 row-major 直觉单独修改。传感器支架位置改变时，需要同时更新 sensor profile 和 mapping config；不得只旋转最终 PCD。

### Initial Pose

RC 没有提供自动全局 seed 的 active 传感器，因此使用 official manual initialization：

```text
RViz 2D Pose Estimate
  -> /initialpose
  -> official RViz adaptor / AD API
  -> /api/localization/initialize
  -> pose initializer
  -> /initialpose3d
  -> EKF Localizer and NDT initialization flow
```

在线模式下 pose initializer 会检查车辆停止状态，因此 `/sensing/vehicle_velocity_converter/twist_with_covariance` 必须持续提供可信零速/低速数据。人工给出的 pose 是局部搜索 seed，NDT Scan Matcher 再使用当前点云与 PCD map 求精确 pose。

### UART Adapter

RC 底盘边界：

```text
/control/command/control_cmd
  -> autoracer_safety/command_gate
  -> /autoracer/control/safe_control_cmd
  -> autoracer_vehicle_interface/rc_serial_interface
  -> 0x7B cmd1 cmd2 vx vy wz bcc 0x7D
  -> STM32 UART4
```

`SERIAL_PORT` 与 `SERIAL_BAUDRATE` 是 runtime 配置，不是架构常量。Adapter 负责串口帧、命令超时和硬件单位转换，并发布 `/vehicle/status/velocity_status`、steering、gear 和 control mode。速度符号、前轮转角、`wz`、deadband 和 firmware 版本必须在动态测试前核对。

### 车辆参数

| 参数 | 值 |
| --- | --- |
| 车长 | `0.83 m` |
| 车宽 | `0.58 m` |
| 车高 | `0.50 m` |
| 轮径 | `0.23 m` |
| 轮半径 / `base_link` 高度 | `0.115 m` |
| 轴距 | `0.6 m` |
| 最大前轮转角 | `0.262 rad` |

这些值必须在 vehicle profile、URDF/TF、official controller 参数和 vehicle adapter 限幅中保持一致。任何修改都要附带低速标定结果，避免多处参数独立漂移。

## Hooke Target Contract

Hooke vehicle/sensor profile 当前为 `pending`，not runtime ready。目标实现仍需遵守与 RC 相同的 shared contract：

- `vehicle_model:=autoracer_hooke` 对应 description 与 launch package。
- `sensor_model:=autoracer_hooke_sensor_kit` 对应 sensor-kit description 与 launch package。
- LiDAR、GNSS/INS/IMU 输出必须转换到 official sensing 与 localization topic。
- 底盘 Adapter 只消费 `/autoracer/control/safe_control_cmd`，并发布完整 `/vehicle/status/*`。
- 传感器外参、车辆参数、CAN 定义和 emergency/gear 能力必须由实物与协议确认。
- 移除 `COLCON_IGNORE` 前，需要 package、标定、静态测试和 on-car 验收形成闭环。

Fixposition 可作为 Hooke 初始位姿与 regularization 的设计来源，目标 topic 包括：

```text
/fixposition/fix
/fixposition/autoware_orientation
/fixposition/rawimu
/fixposition/odometry_enu
/fixposition/speed
```

预期由 `/fixposition/fix` 和 orientation 进入 `autoware_gnss_poser`，形成 `/sensing/gnss/pose_with_covariance`。该链路在 Hooke profile 验证前保持 `pending`，不能描述为当前运行事实。

## Hooke Reference Material

以下目录状态为 `reference`：

| Path | 可提取信息 | 限制 |
| --- | --- | --- |
| `src/hooke2_vehicle` | 车辆消息转换、旧 CAN interface、状态 topic。 | 不符合当前 profile 本身，也可能绕过当前 safety boundary。 |
| `src/hardware_drivers` | SocketCAN `can0` 与 driver 结构。 | 设备名和 `500000 bps` 需要目标底盘复核。 |
| `src/wd_msgs` | chassis message、byte helper、协议字段。 | 必须和目标 firmware/protocol 版本比对。 |
| `src/autoracer_description` | 旧 URDF、frame 和 static transform。 | 数值不能直接作为 Hooke active calibration。 |

参考代码可以被拆解迁移，但不能整体作为正式 Hooke 入口。任何复用都要落入对应 Hooke profile、共享 adapter 或明确的项目 package，并通过 shared topic contract 接入。

## Shared Frames

| Frame relationship | Contract |
| --- | --- |
| `map -> base_link` | localization 运行时动态 TF；低速运动时连续更新。 |
| `base_link -> lidar_top` | 平台 sensor-kit description 中的实测静态 TF。 |
| `base_link -> imu_link` | 平台 sensor-kit description 中的实测静态 TF，轴向与 yaw 对齐必须验证。 |
| `base_link -> gnss_base_link` | 仅在带 GNSS/INS 的 profile 中启用，并以天线参考点实测。 |

`/tf_static` 记录传感器和车体刚性关系，`/tf` 记录 localization 等运行时关系。两者不能互相替代。传感器物理位置变化会同时使运行 TF 与建图外参失效。

这些事实对应的上车检查顺序由 `docs/operations/rc_runbook_zh.md` 统一维护。
