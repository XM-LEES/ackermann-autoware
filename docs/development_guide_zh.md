# 平台开发契约

本文规定平台 profile、底盘 adapter、sensor adapter、自研算法和上游依赖的维护方式。现场操作属于 `docs/operations/`，系统数据流属于 `docs/architecture_zh.md`，接口和标定值属于 `docs/reference/interfaces_and_calibration_zh.md`。

## 平台与状态

RC 与 Hooke 都是 first-class platform target。车型能力通过同一提交内的 profile 和状态表达，不通过长期车型分支表达。

Platform status is commit-scoped。一个提交可以只让一个平台可运行，也可以在共享契约调整期间暂时不让任何平台可运行，但状态必须明确，未就绪入口必须 fail fast。

统一状态词：

| 状态 | 开发含义 |
| --- | --- |
| `active` | 当前默认运行链的一部分，要求构建、启动和运行证据。 |
| `available` | 已接入并可配置启用，要求对应验证。 |
| `available_disabled` | 依赖和装配入口存在，但当前 profile 明确关闭。 |
| `candidate` | 可构建的候选实现，不得被误写成默认模块。 |
| `reference` | 迁移或接口研究材料，不得从其存在推断运行能力。 |
| `pending` | 目标契约已建立，但实现或验证尚不完整。 |

当前平台状态：

| Platform | Status | Vehicle model | Sensor model | Source boundary |
| --- | --- | --- | --- | --- |
| RC | `active` | `autoracer_rc` | `autoracer_rc_sensor_kit` | `src/autoracer_rc_*` |
| Hooke | `pending` | `autoracer_hooke` | `autoracer_hooke_sensor_kit` | `src/autoracer_hooke_*`，由 `COLCON_IGNORE` 保护 |

## Package 职责

### 平台 Profile

| Path | Status | Responsibility |
| --- | --- | --- |
| `src/autoracer_rc_description` | `active` | RC vehicle geometry、`vehicle_info`、URDF/xacro。 |
| `src/autoracer_rc_launch` | `active` | RC vehicle interface、项目 safety gate 和 RViz profile 装配。 |
| `src/autoracer_rc_sensor_kit_description` | `active` | RC LiDAR/IMU sensor-kit URDF 与外参。 |
| `src/autoracer_rc_sensor_kit_launch` | `active` | C32、Hipnuc IMU、Madgwick 和 pointcloud adapter/filter。 |
| `src/autoracer_hooke_description` | `pending` | Hooke vehicle description 占位边界。 |
| `src/autoracer_hooke_launch` | `pending` | Hooke vehicle interface 占位边界。 |
| `src/autoracer_hooke_sensor_kit_description` | `pending` | Hooke sensor-kit description 占位边界。 |
| `src/autoracer_hooke_sensor_kit_launch` | `pending` | Hooke sensing launch 占位边界。 |

### 项目共享 Package

| Path | Status | Responsibility |
| --- | --- | --- |
| `src/autoracer_vehicle_interface` | `active` | 底盘 Adapter、RC UART、vehicle status bridge 和 velocity converter。 |
| `src/autoracer_sensing` | `active` | 保持 official sensing contract 的 sensor adapter。 |
| `src/autoracer_safety` | `active` | 底盘输出前的 enable、limit、timeout 与 stop safety gate。 |

### 候选算法与参考材料

| Path | Category | Status | Responsibility |
| --- | --- | --- | --- |
| `src/autoracer_localization` | local algorithm package | `candidate` | 定位辅助或替换模块，必须显式接入 official contract。 |
| `src/autoracer_planning` | local algorithm package | `candidate` | 规划候选模块，不是默认 official planning。 |
| `src/autoracer_control` | local algorithm package | `candidate` | 控制候选模块，不是默认 official control。 |
| `src/autoracer_description` | reference material | `reference` | 旧 description 与 static TF 迁移参考。 |
| `src/hooke2_vehicle` | reference material | `reference` | Hooke vehicle/CAN 接口参考。 |
| `src/hardware_drivers` | reference material | `reference` | SocketCAN driver 参考。 |
| `src/wd_msgs` | reference material | `reference` | Hooke chassis message 与 byte helper 参考。 |
| `src/external/autoware` | upstream/pinned dependency | pinned | 选定版本的官方 Autoware 源码，原则上只读。 |

`buildable` 只说明 package 可以进入工作区构建，不改变其状态。`scripts/build_minimal.sh` 使用三个显式数组：

- `ACTIVE_RUNTIME_PACKAGES`：当前运行链和 official stack。
- `CANDIDATE_PACKAGES`：可构建但未默认启动的本地算法。
- `REFERENCE_PACKAGES`：为平台接入保留的参考 package 和依赖。

默认只构建 `ACTIVE_RUNTIME_PACKAGES`。只有显式设置 `BUILD_CANDIDATES=true` 或
`BUILD_REFERENCES=true` 时，另外两组才进入本次构建；这两个开关不改变默认运行图。
这些数组描述 `build_minimal.sh` 的构建目标，不是仓库材料目录的完整分类。
例如 `src/hooke2_vehicle`、`src/hardware_drivers` 和 `src/wd_msgs` 可以作为
`reference` 保留，但只有被数组显式列出的 package 才进入 minimal build。

## 新增或修改平台 Profile

每个平台必须实现 official Autoware package 命名契约：

```text
<vehicle_model>_description
<vehicle_model>_launch
<sensor_model>_description
<sensor_model>_launch
```

RC：

```text
vehicle_model:=autoracer_rc
sensor_model:=autoracer_rc_sensor_kit
```

Hooke：

```text
vehicle_model:=autoracer_hooke
sensor_model:=autoracer_hooke_sensor_kit
```

归属规则：

- 车身几何、轴距、转角限制和 vehicle URDF 放在 vehicle description。
- 相对 `base_link` 的传感器外参放在 sensor-kit description。
- 传感器驱动、过滤参数和 sensing launch 放在 sensor-kit launch。
- 底盘 transport 的启动参数放在 vehicle launch，协议实现放在 vehicle adapter。
- 地图路径、串口设备、LiDAR 网卡和 RViz 开关属于 runtime 参数，不写死到 profile。
- 不复用另一车型的包名承载当前车型参数。

Profile 变更的最低检查：

```bash
python3 -m pytest test -q
colcon list --names-only | grep -E '^(autoracer_rc|autoracer_hooke)' || true
```

`colcon list --names-only` 的当前预期是 RC profile 可发现，Hooke package 在 `pending` 阶段不可发现。

## 底盘 Adapter

正式命令边界：

```text
official trajectory follower
  -> official VehicleCmdGate
  -> /control/command/control_cmd
  -> autoracer_safety/command_gate
  -> /autoracer/control/safe_control_cmd
  -> platform adapter
  -> chassis transport
```

底盘 Adapter 必须：

- 消费 gated control command，不绕过项目 safety gate。
- 发布 official `/vehicle/status/*`，保持消息类型、单位、时间戳与 frame 语义。
- 只在 adapter 内处理 CAN、UART、checksum、byte layout 和固件兼容。
- 将设备路径、波特率等作为 runtime 配置；平台硬件常量才进入 profile。
- 对命令超时、drive disabled 和失效输入产生确定的停止行为。
- 使用静态数据、架空轮测试和低速动态测试验证速度符号、转角方向与反馈尺度。

## 自研算法模块

候选模块可以替换 official implementation，但必须保持官方结构：

1. 声明被替换模块、输入/输出 topic、message、frame、QoS 和 diagnostics。
2. 优先使用 upstream plugin/module preset；不支持插件时使用等价 contract 的 node。
3. 不一致接口由薄 adapter 转换，不把转换逻辑散落在算法或 shell 中。
4. 通过正式 launch/profile 参数显式选择，不增加隐藏默认路径。
5. 保留与 official implementation 的可替换性和独立测试。
6. 只有完成目标平台验证，才把状态从 `candidate` 调整为 `available` 或 `active`。

## Upstream 依赖

`src/external/autoware` 是 upstream/pinned dependency，选定源码快照由当前仓库直接
跟踪。普通 clone 已包含这些源码，不对该目录执行 `vcs import`；`autoracer.repos` 只保留
upstream URL 与 revision provenance，更新快照属于显式维护任务。

`scripts/ros_env.sh` 默认移除当前 shell 继承的其他 workspace underlay，再加载 ROS Humble
和当前仓库。确需叠加外部工作区时必须显式设置
`AUTORACER_ALLOW_EXTERNAL_UNDERLAY=true`，并把该 underlay 纳入对应验证记录。

优先通过参数、profile、adapter 或本地 package 解决集成问题；确需补丁时必须记录：

```text
Upstream package and revision
Reason and external constraint
Rejected alternatives
Verification evidence
Reversal or upstreaming path
```

禁止无记录修改后再依赖该行为，也禁止把 upstream package 复制进项目目录形成第二份来源。

## 验证层级

| 变更 | 最低验证 |
| --- | --- |
| 文档和元数据 | 文档契约测试、XML/Python/Bash 静态检查。 |
| Profile 或 launch | x86 静态测试、Orin build、no-hardware smoke。 |
| Sensor/vehicle adapter | Orin build、topic/TF/diagnostics、硬件静态测试。 |
| Localization/planning/control | 地图回放或现场数据、full-chain、低速动态验证。 |
| Upstream patch | 受影响测试、Orin build/runtime、补丁记录。 |

x86 和 Orin 可以有不同的依赖可用性，但必须使用同一 commit。真实 ARM64 launch、硬件依赖和运行行为以 Orin 证据为准。

## 文档维护规则

| 内容 | 唯一正文位置 |
| --- | --- |
| 项目定位、平台状态、目录结构、文档索引 | `README.md` |
| 系统模块、runtime 数据流和平台边界 | `docs/architecture_zh.md` |
| 平台与 package 开发契约 | `docs/development_guide_zh.md` |
| 现场启动、停止和验收命令 | `docs/operations/` |
| Topic、frame、硬件接口与标定值 | `docs/reference/interfaces_and_calibration_zh.md` |
| 可交互架构投影 | `docs/architecture/project_architecture.html` |

维护要求：

- 直接陈述当前事实、契约和状态，不保存迁移叙事或调试流水账。
- 不在稳定文档中写开发者绝对路径、凭据、临时主机地址或 feature branch 名称。
- 操作命令只放 operations，数值事实只放 reference，避免多份文档漂移。
- HTML 架构页是 `architecture_zh.md` 的可视化投影，不能自行定义第二套事实。
- 新增正式文档前先确认现有职责无法承载；优先更新或合并，不增加索引层。

文档和仓库契约检查：

```bash
python3 -m pytest test/test_docs_architecture_contract.py -q
python3 -m pytest test -q
```
