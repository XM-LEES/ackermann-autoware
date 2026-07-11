# Ackermann Autoware 系统架构

本文定义当前系统的运行主线、Autoware 装配方式、平台接入边界和算法替换契约。仓库目录职责由根目录 `README.md` 说明；现场命令由 `docs/operations/` 维护；topic、frame、硬件和标定值由 `docs/reference/interfaces_and_calibration_zh.md` 维护。

## 项目边界

本项目是面向 Ackermann 车辆的 Autoware 集成工作区。RC 和 Hooke 是同一系统中的两个 first-class platform target，共享 official Autoware 上层能力，通过各自的 vehicle profile、sensor-kit profile、标定和底盘 adapter 接入。

系统所有权分为三层：

```text
平台层      vehicle/sensor profile、driver、calibration、vehicle adapter
项目共享层  sensor adapter、最终 safety gate、operations、mapping/system tools
官方层      Map、Localization、Perception、Planning、Control、AD API、System
```

边界约束：

- 平台差异只进入 profile、calibration、adapter 和对应 operation runbook。
- 共享算法遵守 official topic、message、frame、parameter、QoS 与 diagnostics contract。
- `src/external/autoware` 是 pinned upstream dependency；不在 `src/external/autoware` 里做隐形修改。
- 上游补丁必须记录来源 revision、原因、验证和撤销路径。
- Shell 脚本是薄入口，不承担算法装配逻辑，也不隐藏车型差异。

## 系统主线

当前运行架构围绕车辆从地图和传感器输入到真实底盘执行的闭环组织：

```text
                              Map
                        +------+------+
                        |             |
                        v             v
Sensing ----------> Localization     Planning ----------> Control
  |                       |              ^                   |
  |                       +--------------+                   v
  +--> Perception (available_disabled) --+           VehicleCmdGate
                                                            |
                                                            v
                                                  Project Safety Gate
                                                            |
                                                            v
                                                   Vehicle Adapter
                                                            |
                                                            v
                                                         Chassis

/vehicle/status/* -> Localization / Control
```

贯穿主线的管理能力：

```text
AD API               initialization / route / operation mode / state
System / Diagnostics node health / host monitor / diagnostics graph
```

Autoware 中 Sensing 与 Perception 是两个独立层次：

- Sensing 负责 driver、格式转换、过滤、时间戳和 sensor TF。
- Perception 负责 objects、obstacles、traffic lights 等环境语义。

功能关系是 Perception (available_disabled) -> Planning；当前该支路没有运行。RC 当前 Sensing 为 `active`，Perception 为 `available_disabled`。因此当前有效闭环是 Map/Sensing、Localization、Planning、Control 和底盘反馈；不能把已装配的 perception 边界解释为感知能力已经投入运行。

## 能力状态

统一状态词用于区分“源码存在”“能够构建”和“当前默认运行”：

| 状态 | 含义 |
| --- | --- |
| `active` | 当前 profile 默认启动，并有对应运行契约。 |
| `available` | 已集成且可按配置启用，但不是当前默认路径。 |
| `available_disabled` | 依赖和装配入口存在，当前配置明确关闭。 |
| `candidate` | 可构建的候选实现，未进入默认运行链。 |
| `reference` | 仅用于迁移、接口研究或参数比对，不是运行实现。 |
| `pending` | 目标边界已定义，但 profile 尚不具备运行条件。 |

Platform runtime status is commit-scoped。每个提交必须如实表达两套平台的运行状态，不以分支名称代表车型能力。

| 能力 | 当前状态 | 说明 |
| --- | --- | --- |
| RC platform | `active` | official profile、传感器、手动初始化和串口底盘链已装配。 |
| Hooke platform | `pending` | 占位目录由 `COLCON_IGNORE` 保护，not runtime ready。 |
| Map | `active` | PCD、Lanelet2 和 projector 由 official map launch 加载。 |
| Sensing | `active` | RC C32、IMU 和项目 sensor adapter 已接入。 |
| Localization | `active` | NDT Scan Matcher、Gyro Odometer、EKF Localizer、Stop Filter。 |
| Perception | `available_disabled` | official 入口可用，RC 默认 `launch_perception:=false`。 |
| Planning | `active` | 默认使用 official Autoware planning。 |
| Control | `active` | 默认使用 official Autoware control 和 VehicleCmdGate。 |
| AD API | `active` | initialization、route/goal、operation mode 与状态接口。 |
| System / Diagnostics | `active` | official system monitor 与 diagnostics graph。 |
| 本地 localization/planning/control | `candidate` | 仅在显式替换并验证后进入运行链。 |
| Hooke 旧包和硬件代码 | `reference` | 实现 Hooke profile 的输入资料。 |

## Profile 装配

顶层入口使用 official `autoware_launch/autoware.launch.xml`。Autoware 根据 `vehicle_model` 和 `sensor_model` 查找四类 profile package：

| 角色 | 命名契约 | RC 实现 |
| --- | --- | --- |
| Vehicle description | `<vehicle_model>_description` | `autoracer_rc_description` |
| Vehicle launch | `<vehicle_model>_launch` | `autoracer_rc_launch` |
| Sensor-kit description | `<sensor_model>_description` | `autoracer_rc_sensor_kit_description` |
| Sensor-kit launch | `<sensor_model>_launch` | `autoracer_rc_sensor_kit_launch` |

RC 装配参数：

```text
vehicle_model:=autoracer_rc
sensor_model:=autoracer_rc_sensor_kit
```

这些是 profile 选择契约，不是独立启动命令。可执行启动流程由
`docs/operations/rc_runbook_zh.md` 维护，运行时还必须提供地图和硬件参数。

Hooke 遵循相同命名契约：

```text
vehicle_model:=autoracer_hooke
sensor_model:=autoracer_hooke_sensor_kit
```

Hooke profile 当前为 `pending`，四个目录由 `COLCON_IGNORE` 保护。只有 description、sensing launch、vehicle launch、adapter、标定和验收信息形成完整闭环后，才可以移除保护并声明可运行。

## Map 与 Profile

Map 是共享运行输入，不属于某个平台的私有 bringup：

| 资产 | 主要消费者 | 责任 |
| --- | --- | --- |
| `pointcloud_map.pcd` + metadata | Localization | NDT 点云匹配与动态地图加载。 |
| `lanelet2_map.osm` | Planning | route、道路拓扑和行为规则。 |
| `map_projector_info.yaml` | Map loaders | 点云和矢量地图的坐标定义。 |

Profile 只表达平台事实：

```text
vehicle description    geometry / wheelbase / steering limits / vehicle URDF
sensor-kit description sensor extrinsics / sensor URDF
sensor-kit launch      drivers / filters / format adapters
vehicle launch         safety gate / vehicle adapter wiring
```

地图路径、串口设备、LiDAR 网卡、RViz 和 drive enable 是 runtime 配置，不写死到 profile。

## Sensing 与 Perception

RC active sensing chain：

```text
Leishen C32
  -> lslidar_driver
  -> /sensing/lidar/raw/pointcloud
  -> c32_pointcloud_adapter (PointXYZIRC)
  -> /sensing/lidar/concatenated/pointcloud

Hipnuc IMU
  -> /sensing/imu/imu_data_raw
  -> imu_filter_madgwick
  -> /sensing/imu/imu_data
```

`c32_pointcloud_adapter` 是 C32 raw layout 与 official PointXYZIRC contract 之间的薄边界。`/sensing/lidar/filtered/pointcloud` 只用于诊断、远程显示和建图辅助；official localization 默认消费 concatenated topic。

Perception 当前配置：

```text
launch_perception=false
status=available_disabled
```

Perception 启用后从 Sensing 获取点云等输入，并向 Planning 提供 objects/obstacles/traffic-light semantics。当前没有这些真实输入，因此不能声明动态障碍物感知或完整避障能力。

## Localization

RC 没有 active 的自动全局定位传感器，通过 official AD API 手动初始化：

```text
RViz /initialpose
  -> official RViz adaptor
  -> /api/localization/initialize
  -> pose_initializer
  -> /initialpose3d
```

Pose 与 twist 分开估计，再由 EKF 融合：

```text
PCD map + concatenated pointcloud + initial seed
  -> NDT Scan Matcher
  -> /localization/pose_estimator/pose_with_covariance

/vehicle/status/velocity_status
  -> vehicle_velocity_converter
  -> /sensing/vehicle_velocity_converter/twist_with_covariance
  + /sensing/imu/imu_data
  -> Gyro Odometer
  -> /localization/twist_estimator/twist_with_covariance

pose + twist + /initialpose3d
  -> EKF Localizer
     |-> /localization/pose_with_covariance
     `-> /localization/pose_twist_fusion_filter/kinematic_state
           -> Stop Filter
           -> /localization/kinematic_state
```

NDT 只产生 pose estimator 输出，不直接生成最终 `kinematic_state`。人工初始位姿用于限定搜索范围，NDT 再利用现场点云和 PCD map 求精确 pose。

## Planning

当前默认使用 official planning：

```text
Lanelet2 + route/goal + /localization/kinematic_state
  + optional Perception semantics
  -> Mission Planning
  -> Behavior Path / Behavior Velocity Planning
  -> Motion Path Smoother / Path Optimizer
  -> Velocity Smoother
  -> Planning Validator
  -> /planning/trajectory
```

Pinned default preset 选择 Elastic Band、Path Optimizer 和 JerkFiltered Velocity Smoother。本地 `autoracer_planning` 是 `candidate`，不进入默认运行链。

Planning module 被启动不等于所有场景已经验证。Perception 关闭时，依赖 objects、obstacle pointcloud 或 traffic-light 输入的 module 没有完整数据，不能据此声明动态避障能力。

## Control、Gate 与 Vehicle Feedback

当前 official control 使用 trajectory follower；pinned default 为 MPC lateral control 和 PID longitudinal control：

```text
/planning/trajectory + /localization/kinematic_state
  -> official trajectory follower
  -> official VehicleCmdGate
  -> /control/command/control_cmd
  -> autoracer_safety/command_gate
  -> /autoracer/control/safe_control_cmd
  -> platform vehicle adapter
  -> UART or CAN
  -> chassis
```

两层 gate 的责任不同：

| Gate | 责任 |
| --- | --- |
| Official VehicleCmdGate | operation mode、autonomous/external/emergency command arbitration。 |
| Project Safety Gate | drive enable、速度/转角限制、命令超时和底盘输出前停止边界。 |

平台 adapter 必须消费 `/autoracer/control/safe_control_cmd`，将 UART/CAN/checksum/private protocol 限制在 adapter 内，并发布：

```text
/vehicle/status/velocity_status
/vehicle/status/steering_status
/vehicle/status/gear_status
/vehicle/status/control_mode
```

反馈闭环：

```text
chassis -> platform adapter -> /vehicle/status/* -> Localization / Control
```

RC active adapter 是 `rc_serial_interface`；Hooke 目标 CAN adapter 当前为 `pending`。所有 status 必须保持 official message、单位、时间戳和 frame 语义。

## AD API、System 与 Diagnostics

AD API 提供 operator-facing contract：

```text
localization initialize / route / operation mode / state
```

Official RViz plugins 是 AD API 和状态 topic 的 client，不是另一套 autonomy algorithm。Foxglove Bridge 只负责远程 topic/pointcloud 观察，也不拥有 operation mode。

System / Diagnostics 横跨所有运行模块：

```text
node diagnostics -> diagnostics graph -> system state
host/network monitors -> System / Diagnostics
```

这些 API、monitor 和 validator 是完整 Autoware graph 节点数量增加的重要来源。它们不属于某个单一算法层，但决定系统是否能够被操作、诊断和安全放行。

## 算法扩展边界

`src/autoracer_localization`、`src/autoracer_planning` 和 `src/autoracer_control` 是 `candidate` package。源码存在和能够构建不代表被默认启动。

自研算法接入规则：

1. 声明被替换的 official component 和输入/输出 contract。
2. 优先使用 official plugin 或 module preset；否则使用相同 contract 的 node。
3. 接口不一致时只增加薄 adapter，并明确单位、frame、QoS 和 diagnostics 转换。
4. 在 profile 或正式 launch 中显式选择，不在 `scripts/` 中隐藏切换逻辑。
5. Control 无论来源如何，都必须经过 official VehicleCmdGate 和 Project Safety Gate。
6. 完成回归、no-hardware smoke、数据回放和目标平台验证后，才调整状态。

## 开发与部署

```text
x86 development and mapping
  source inspection / tests / bag processing / map preparation
                    |
                    | git commit + map sync
                    v
Orin onboard runtime
  ARM64 build / profiles / sensors / Autoware / chassis adapter
```

- x86 负责开发、测试、rosbag 离线处理和地图生产，不要求构建全部 ARM/硬件依赖。
- Orin 是 launch、依赖和硬件接口的运行判定环境。
- 两端以同一 commit 为基线，车型差异通过 profile 表达，不通过长期分叉复制代码。
- `scripts/rc/` 提供 RC operation entrypoint。
- `scripts/hooke/` 在 Hooke `pending` 期间 fail fast。
- `scripts/common/` 只保存无车型事实的共享逻辑。

## 可视化架构

离线项目架构浏览页：

```text
docs/architecture/project_architecture.html
```

该文件直接在浏览器打开，不依赖 CDN 或 Mermaid。它提供项目总览、共享 runtime、RC 链路、部署与扩展四个视图。HTML 是本文的可视化投影，不是 on-car HMI，也不独立定义第二套架构事实；正文和实现变化时必须同步更新。
