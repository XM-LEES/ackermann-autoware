# RC 上车运行手册

用途：给现场运行者一个可重复的上车检查、启动、定位、规划、控制和低速验证流程。非用途：不讨论官方 Autoware 迁移，不记录一次性小测试。

目标：按 RC 平台 profile 启动 official Autoware planning/control、command gate 和 RC vehicle adapter，并完成定位、规划、控制和低速安全检查。

本文件只写现场操作步骤；架构边界看 `docs/architecture_zh.md`，topic、frame、车辆参数和标定事实看 `docs/reference/interfaces_and_calibration_zh.md`。

## 0. 可复制启动命令

以下命令在 Orin 车端仓库执行。每个新终端先执行“公共变量”块；切换
localization-only、full-chain dry-run、drive-enabled 三种模式前都先执行
`./scripts/rc/rc_stop.sh`，不要把 localization-only 和 full-chain 连续叠加启动。
`/initialpose` 是 RViz 操作入口；`/initialpose3d` 是 official localization 内部入口。
脚本默认保留官方 API/RViz adaptor，让 localization-only 和 full-chain 的初始定位操作一致。

### 0.1 公共变量

```bash
cd ~/Desktop/autoracer_hooke
set -e

export MAP_NAME=floor1_mapping_001
export MAP_PATH="$PWD/maps/$MAP_NAME"
export IMU_SERIAL_PORT=/dev/ttyUSB0
export SERIAL_PORT=/dev/ttyCH343USB0
export LAUNCH_RVIZ=true

test -f "$MAP_PATH/pointcloud_map.pcd" || test -d "$MAP_PATH/pointcloud_map.pcd"
test -f "$MAP_PATH/pointcloud_map_metadata.yaml"
test -f "$MAP_PATH/lanelet2_map.osm"
test -f "$MAP_PATH/map_projector_info.yaml"
```

### 0.2 传感器检查

终端 A：

```bash
cd ~/Desktop/autoracer_hooke
./scripts/rc/rc_stop.sh
IMU_SERIAL_PORT=/dev/ttyUSB0 \
LAUNCH_RVIZ=false \
./scripts/rc/rc_start_sensors.sh
```

终端 B：

```bash
cd ~/Desktop/autoracer_hooke
./scripts/check_mapping_inputs.sh
./scripts/rc/rc_stop.sh
```

### 0.3 定位单链路

终端 A：

```bash
cd ~/Desktop/autoracer_hooke
./scripts/rc/rc_stop.sh
MAP_PATH="$PWD/maps/$MAP_NAME" \
IMU_SERIAL_PORT=/dev/ttyUSB0 \
LAUNCH_RVIZ=true \
./scripts/rc/rc_start_localization.sh
```

终端 B：

```bash
cd ~/Desktop/autoracer_hooke
source scripts/ros_env.sh
ros2 topic hz /sensing/lidar/concatenated/pointcloud --window 5
ros2 topic list | rg '/localization/(pose_with_covariance|kinematic_state)'
ros2 topic list | rg '/initialpose3d|/api/localization/initialize'
```

在 RViz 或等价工具里发布 `/initialpose`。官方 RViz adaptor 会调用 AD API，
再由 pose initializer 发布 `/initialpose3d` 给 localization。随后检查：

```bash
ros2 topic echo /initialpose3d --once
ros2 topic hz /localization/pose_with_covariance --window 5
ros2 run tf2_ros tf2_echo map base_link
```

收尾：

```bash
cd ~/Desktop/autoracer_hooke
./scripts/rc/rc_stop.sh
```

### 0.4 完整链路，不放行底盘

终端 A：

```bash
cd ~/Desktop/autoracer_hooke
./scripts/rc/rc_stop.sh
MAP_PATH="$PWD/maps/$MAP_NAME" \
IMU_SERIAL_PORT=/dev/ttyUSB0 \
SERIAL_PORT=/dev/ttyCH343USB0 \
LAUNCH_RVIZ=true \
ENABLE_DRIVE_COMMANDS=false \
./scripts/rc/rc_start_autoware.sh
```

终端 B：

```bash
cd ~/Desktop/autoracer_hooke
source scripts/ros_env.sh
ros2 topic list | rg '/planning/trajectory|/control/command/control_cmd|/autoracer/control/safe_control_cmd|/vehicle/status'
```

确认初始位姿、短 route/goal、trajectory、control、safe control 都正常后收尾：

```bash
cd ~/Desktop/autoracer_hooke
./scripts/rc/rc_stop.sh
```

### 0.5 低速放行底盘

只在定位、短 route、转角方向、速度符号、停止行为都确认后执行：

```bash
cd ~/Desktop/autoracer_hooke
./scripts/rc/rc_stop.sh
MAP_PATH="$PWD/maps/$MAP_NAME" \
IMU_SERIAL_PORT=/dev/ttyUSB0 \
SERIAL_PORT=/dev/ttyCH343USB0 \
LAUNCH_RVIZ=true \
ENABLE_DRIVE_COMMANDS=true \
MAX_SPEED_MPS=0.5 \
./scripts/rc/rc_start_autoware.sh
```

另开终端请求 autonomous mode：

```bash
cd ~/Desktop/autoracer_hooke
source scripts/ros_env.sh
./scripts/request_autonomous_mode.sh
```

停车收尾：

```bash
cd ~/Desktop/autoracer_hooke
./scripts/rc/rc_stop.sh
```

### 0.6 Foxglove 实时监控

Foxglove Bridge 在 Orin 的独立终端运行，必须使用与 Autoware 相同的仓库环境：

```bash
cd ~/Desktop/autoracer_hooke
source scripts/ros_env.sh
ros2 launch foxglove_bridge foxglove_bridge_launch.xml
```

客户端连接 `ws://192.168.1.135:8765/`。结束时在该终端按 `Ctrl-C`；
`./scripts/rc/rc_stop.sh` 不停止独立运行的 Foxglove Bridge。

## 1. 主机与网络

- 车端仓库必须和当前开发基线在同一 commit；当前基线分支是 `feature/official-autoware-launch`。
- 车端已构建或至少能 source workspace。
- 车端 DDS 内核参数和 official system monitor 特权网络读取服务已配置：

```bash
sudo -E ./tools/system/configure_onboard_host.sh
sysctl net.core.rmem_max net.core.rmem_default \
  net.ipv4.ipfrag_time net.ipv4.ipfrag_high_thresh
systemctl is-active autoracer-traffic-reader.service
test -S /tmp/traffic_reader
```

该配置跟随 Autoware 官方 DDS 大消息建议：CycloneDDS 仅在车端 loopback 上传输 ROS
进程数据，远程可视化通过 Foxglove Bridge 的 WebSocket 进入；C32 UDP 仍走专用网口。
主机服务负责运行上游 `traffic_reader` 和 `nethogs`，不会由 `rc_stop.sh` 反复启停。
- LiDAR-facing 网口配置完成：

```bash
sudo -E ./scripts/rc/rc_configure_lidar.sh
```

- 临时主机信息不写入仓库。

## 2. 传感器与 TF

启动 mapping/定位所需传感器：

```bash
IMU_SERIAL_PORT=/dev/ttyUSB0 ./scripts/rc/rc_start_sensors.sh
```

检查输入：

```bash
./scripts/check_mapping_inputs.sh
```

验收项：

- C32 driver 输出 `/sensing/lidar/raw/pointcloud`。
- `c32_pointcloud_adapter` 输出 `/sensing/lidar/concatenated/pointcloud`，字段布局为 Autoware `PointXYZIRC`。
- 点云 frame 为 `lidar_top`。
- Hipnuc IMU 输出 `/sensing/imu/imu_data_raw` 和 `/sensing/imu/imu_data`。
- `base_link -> lidar_top` 和 `base_link -> imu_link` 可查。
- RC LiDAR/IMU 使用 sensor profile 中的 2026-07-10 静止标定值；传感器物理位置变化后必须重新标定。

## 3. 底盘反馈

串口节点应发布：

- `/vehicle/status/velocity_status`
- `/sensing/vehicle_velocity_converter/twist_with_covariance`
- `/vehicle/status/steering_status`
- `/vehicle/status/gear_status`
- `/vehicle/status/control_mode`

`/sensing/vehicle_velocity_converter/twist_with_covariance` 是 official pose initializer 的 stopped-check 输入。它必须有连续零速数据，否则 RViz 里点击初始位姿会被 `/api/localization/initialize` 拒绝。

若串口协议未变，现有固件可先测链路。物理标定前必须确认固件版本、车身参数、速度尺度、转角尺度和 deadband。

## 4. 地图

完整地图目录必须包含：

```text
pointcloud_map.pcd/   # 分块目录；小地图也可以是单个 PCD 文件
pointcloud_map_metadata.yaml
lanelet2_map.osm
map_projector_info.yaml
```

official localization-only 也需要完整地图目录；缺少 Lanelet2 或 projector 资产时先补齐地图，不声明车端 localization 已可验证。

超过 128 MiB 的单个 PCD 会被启动脚本拒绝。正式运行地图应通过
`tools/mapping/prepare_autoware_pointcloud_map.sh` 降采样和分块，metadata 由官方
divider 生成，不手写。

## 5. Localization

启动 localization-only：

```bash
MAP_PATH=~/Desktop/autoracer_hooke/maps/<map_name> \
IMU_SERIAL_PORT=/dev/ttyUSB0 \
./scripts/rc/rc_start_localization.sh
```

验收项：

- RViz/ROS 发布 `/initialpose`；official API/RViz adaptor 将其送入 AD API，
  pose initializer 再发布 `/initialpose3d`。
- `/localization/pose_with_covariance` 持续更新。
- `/localization/kinematic_state` 有输出。
- `map -> base_link` TF 稳定。

车辆不在所选地图覆盖场景内时，`Localization Uninitialized` 和缺少
`map -> base_link` 属于预期状态；此时只验证地图加载、传感器和其余节点，不判断
NDT 收敛。

不使用 AMCL/slam_toolbox。

## 6. Planning

- 当前分支默认由 `autoware_launch` 启动官方 planning。
- 输入完整官方地图目录、localization 状态和 RViz/Autoware route/goal 操作。
- 输出 `/planning/trajectory`。
- 第一轮只用简单短路线。

自研 planning/control 候选不作为本分支默认入口；如果要评估，必须作为单独替换任务显式接入同一 topic/message/frame 合约。

## 7. Control/Gate/Adapter

- 官方 control 输出 `/control/command/control_cmd`。
- `command_gate` 读取 `/control/command/control_cmd`，默认禁用时输出 stop。
- `command_gate` 的 adapter-facing control 输出是 `/autoracer/control/safe_control_cmd`，support commands 仍在 `/control/command/*` 表面。
- `rc_serial_interface` 消费 `/autoracer/control/safe_control_cmd` 并转成 STM32 串口帧。
- 默认 `ENABLE_DRIVE_COMMANDS=false`。
- 当前 Orin RC 车的 STM32 下位机 USB-UART 是 `/dev/ttyCH343USB0`。
- 第一轮实车建议 `MAX_SPEED_MPS=0.5~0.8`。

完整启动：

```bash
MAP_PATH=~/Desktop/autoracer_hooke/maps/<map_name> ./scripts/rc/rc_start_autoware.sh
```

低速使能前必须完成标定检查：

```bash
MAP_PATH=~/Desktop/autoracer_hooke/maps/<map_name> SERIAL_PORT=/dev/ttyCH343USB0 ENABLE_DRIVE_COMMANDS=true ./scripts/rc/rc_start_autoware.sh
./scripts/request_autonomous_mode.sh
```

停止 RC Autoware 相关节点：

```bash
./scripts/rc/rc_stop.sh
```

不要用 `timeout -s INT` 作为 full-chain dry-run 的正式停止方式。它会直接向官方 launch 发送 SIGINT，可能在 composable node 卸载时触发上游 planning container shutdown 崩溃；现场和验证脚本都应让链路正常运行，再用 `rc_stop.sh` 做受控清理。

## 8. 低速动态验证顺序

1. 接 LiDAR、控制板、底盘动力。
2. 烧录最新 STM32 固件，或确认当前固件协议和车身参数与源码一致。
3. 配置 LiDAR 网口。
4. 启动 sensors，跑 `check_mapping_inputs.sh`。
5. 设置 `MAP_PATH`。
6. 启动 official Autoware wrapper，保持 `ENABLE_DRIVE_COMMANDS=false`。
7. 给 `/initialpose`，确认 `/initialpose3d`、NDT 和 TF。
8. 给短 route/goal，确认 trajectory、official control 和 gated safe control。
9. 架空或低速场地设置 `ENABLE_DRIVE_COMMANDS=true`。
10. 验证速度符号、转角方向、停止行为，再提高测试复杂度。
