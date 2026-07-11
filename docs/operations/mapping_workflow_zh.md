# RC 建图与地图发布

本文定义 RC 平台从车端录包到 Autoware 地图发布的标准流程。车端负责采集，x86
工作机负责离线检查、Super-LIO 建图和点云地图预处理，Orin 只使用发布完成的地图。
上车导航命令见 `docs/operations/rc_runbook_zh.md`；topic、frame 和外参契约见
`docs/reference/interfaces_and_calibration_zh.md`。

## 目录边界

版本库保存可复现工具和配置：

```text
autoracer_hooke/tools/mapping/
  mapping.repos
  config/rc_c32_super_lio.yaml
  bootstrap_mapping_ws.sh
  inspect_bag_topics.sh
  run_super_lio_offline.sh
  prepare_autoware_pointcloud_map.sh
  sync_map_to_vehicle.sh
```

工作区和数据不属于源码：

```text
<repo-parent>/rc_mapping_ws/                   # 可重新构建的 x86 colcon 工作区
<repo-parent>/rc_mapping_data/
  bags/raw/<bag_id>/                           # 原始数据，长期保留
  runs/<run_id>/                               # 可重建的 Super-LIO 输出
  autoware_maps/<map_name>/                    # 待标注或可发布地图
```

不要在 `rc_mapping_ws` 内维护正式脚本或配置。依赖版本由
`tools/mapping/mapping.repos` 固定；修改建图行为时必须修改正式仓库并提交。

## 车端采集

以下命令在 Orin 的 `autoracer_hooke` 仓库根目录执行。

### 1. 检查传感器

```bash
IMU_SERIAL_PORT=/dev/ttyUSB0 ./scripts/rc/rc_start_sensors.sh
```

另开一个 SSH 会话：

```bash
cd ~/Desktop/autoracer_hooke
./scripts/check_mapping_inputs.sh
```

检查项包括：

- `/sensing/lidar/raw/pointcloud` 包含 `x/y/z/intensity/ring/time`。
- `/sensing/lidar/concatenated/pointcloud` 是 Autoware `PointXYZIRC` 布局。
- `/sensing/imu/imu_data_raw` 和 `/sensing/imu/imu_data` 持续发布。
- `/tf_static` 包含 RC sensor profile 的 LiDAR 和 IMU 外参。

检查后停止：

```bash
./scripts/rc/rc_stop.sh
```

### 2. 短包验证

```bash
BAG_DURATION_SEC=60 \
RUN_ID=floor_test_001 \
IMU_SERIAL_PORT=/dev/ttyUSB0 \
./scripts/rc/rc_capture_mapping_bag.sh
```

短包只验证数据契约，不作为正式地图。录制开始后车辆至少静止 3 秒，再开始运动，
保证 Super-LIO 的初始重力估计不混入车辆加速度。

### 3. 正式录制

开始：

```bash
RUN_ID=floor1_mapping_001 \
IMU_SERIAL_PORT=/dev/ttyUSB0 \
./scripts/rc/rc_start_mapping_bag.sh
```

确认 recorder 已启动后保持车辆静止至少 3 秒，再低速完成路径。结束：

```bash
./scripts/rc/rc_stop_mapping_bag.sh
```

录包链路不会启动 localization、planning、control 或 vehicle interface，且
`ENABLE_DRIVE_COMMANDS=false`。
启动脚本在 `/tmp/autoracer_rc/mapping_bag.env` 记录 recorder 和 sensor process group
的 PID、启动标识、PGID、用户和仓库路径；停止脚本只有在这些身份全部匹配时才发送
信号，陈旧状态文件不会用于终止其他进程。

正式 bag 包含：

```text
/sensing/lidar/raw/pointcloud
/sensing/lidar/concatenated/pointcloud
/sensing/lidar/filtered/pointcloud
/sensing/imu/imu_data_raw
/sensing/imu/imu_data
/tf
/tf_static
/rosout
```

Super-LIO 优先使用保留逐点时间的 raw 点云。检查工具只对旧 bag 兼容
`/sensing/lidar/concatenated/pointcloud` 和 `/imu/data`；新 bag 不应依赖该兼容路径。

### 4. 拉回工作机

在 x86 仓库根目录执行：

```bash
export MAPPING_DATA_DIR="$(dirname "$PWD")/rc_mapping_data"
VEHICLE_HOST='wheeltec@<orin-host>' \
VEHICLE_BAG=~/autoracer_mapping_bags/floor1_mapping_001 \
./scripts/pull_mapping_bag.sh
```

默认保存到：

```text
${MAPPING_DATA_DIR}/bags/raw/floor1_mapping_001/
```

## 可选实时检查

Foxglove Bridge 只用于现场查看车端点云、IMU、TF 和 diagnostics，不替代 rosbag，
也不是 Autoware 操作界面。传感器启动后，在 Orin 的另一终端执行：

```bash
cd ~/Desktop/autoracer_hooke
source scripts/ros_env.sh
ros2 launch foxglove_bridge foxglove_bridge_launch.xml
```

Bridge 必须与当前 Autoware 使用相同的 RMW 和 CycloneDDS 配置；只 source
`/opt/ros/humble/setup.bash` 会回到默认 Fast DDS，客户端虽能连接端口但看不到当前
Autoware ROS 图。

客户端连接：

```text
ws://<orin-ip>:8765/
```

结束时在 bridge 终端按 `Ctrl-C`；不要在正式录包过程中反复重启传感器链路。

## 工作机离线建图

以下命令在 x86 仓库根目录执行。先统一工作目录变量；mapping helper 的默认值也是
仓库同级目录，显式设置便于日志和人工命令保持一致：

```bash
export REPO_ROOT="$PWD"
export MAPPING_WS="$(dirname "$REPO_ROOT")/rc_mapping_ws"
export MAPPING_DATA_DIR="$(dirname "$REPO_ROOT")/rc_mapping_data"
```

### 1. 准备工具工作区

```bash
./tools/mapping/bootstrap_mapping_ws.sh
```

脚本按 `mapping.repos` 固定版本准备 Super-LIO、其消息依赖和官方
`autoware_pointcloud_divider`。它不修改 Orin 运行工作区。

### 2. 检查 bag

```bash
./tools/mapping/inspect_bag_topics.sh \
  "$MAPPING_DATA_DIR/bags/raw/floor1_mapping_001"
```

检查必须通过字段类型、整帧逐点时间范围、IMU 和静态 TF。Foxglove 用于人工确认
点云、IMU 和时间轴；它不是 Autoware 运行界面。

### 3. 运行 Super-LIO

```bash
PLAYBACK_RATE=1.0 \
./tools/mapping/run_super_lio_offline.sh \
  "$MAPPING_DATA_DIR/bags/raw/floor1_mapping_001" \
  floor1_mapping_001
```

输出目录：

```text
rc_mapping_data/runs/floor1_mapping_001/
  bag_inspection.txt
  selected_topics.env
  rc_c32_super_lio.yaml
  super_lio_commit.txt
  super_lio_status.txt
  super_lio.log
  bag_play.log
  map/map.pcd
  map/quality_report.json
```

每次 run 使用新 ID；脚本不会覆盖已有 run。

### 4. 点云质量门槛

Super-LIO 脚本会自动运行平路地图质量门禁并生成
`map/quality_report.json`。也可以独立复查：

```bash
./tools/mapping/audit_pointcloud_map.py \
  "$MAPPING_DATA_DIR/runs/floor1_mapping_001/map/map.pcd" \
  --output /tmp/floor1_mapping_001_quality.json
```

自动门禁检查 PCD 格式、有限值、全零点、实际范围、主地面比例、主地面倾角和拟合
残差。平路默认最大主地面倾角为 `3.0 deg`；真实坡道数据必须依据测量事实显式设置
`MAX_GROUND_TILT_DEG`，不能为了让错误地图通过而放宽阈值。

自动门禁通过后仍需人工检查：

- 平路主地面方向与重力一致；明显整体倾斜表示外参或初始化错误。
- 同一墙面和路缘没有持续扩散或双层重影。
- 转弯前后结构连续，没有跳变、折叠或断层。
- 路径终点没有随距离增长的明显高度或航向漂移。
- `super_lio.log` 中没有字段、时间同步、NaN 或地图保存错误。

静止短包只能验证流程，不能通过运动地图质量门槛。质量不通过时先修正配置并从原始
bag 重跑，不要通过旋转最终 PCD 掩盖算法或外参错误。

## Autoware 地图目录生成

只有通过质量门槛的 Super-LIO PCD 才能进入该步骤：

```bash
LEAF_SIZE=-0.1 GRID_SIZE=20.0 \
./tools/mapping/prepare_autoware_pointcloud_map.sh \
  floor1_mapping_001 \
  floor1_mapping_001
```

该脚本调用官方 `autoware_pointcloud_divider`，生成：

```text
rc_mapping_data/autoware_maps/floor1_mapping_001/
  pointcloud_map.pcd/              # 20 m 分块 PCD
  pointcloud_map_metadata.yaml     # 工具按实际分块自动生成
  map_projector_info.yaml
  quality_report.json              # 分块前原始 PCD 的自动质量报告
```

`LEAF_SIZE` 和 `GRID_SIZE` 的单位均为米。`LEAF_SIZE=-0.1` 表示默认不额外降采样，
只把完整 Super-LIO PCD 切成便于动态加载的网格；只有性能数据证明完整地图无法运行时，
才显式设置正数体素尺寸。不要手写 `pointcloud_map_metadata.yaml`。输出目录已存在时
脚本默认拒绝覆盖。生成结束后，脚本会校验 metadata 是否完整覆盖每个 PCD 的实际
XY 范围；全部检查通过后才把临时目录发布为正式地图。检查失败时会清理半成品，
不产出可同步地图。

## Lanelet2 标注

Lanelet 必须基于最终分块前所使用的同一坐标系点云标注。不要先标旧 PCD，再替换或
调平点云。标注完成后，将结果保存为同一地图目录中的：

```text
lanelet2_map.osm
```

完整可发布目录必须同时包含：

```text
pointcloud_map.pcd/                 # 也兼容小地图的单个 PCD 文件
pointcloud_map_metadata.yaml
lanelet2_map.osm
map_projector_info.yaml
```

只有点云和 metadata 时属于 localization-only 中间产物，不能声明完整导航地图。

## 同步 Orin

同步脚本会在上传前检查四项地图资产：

```bash
MAPPING_DATA_DIR="$MAPPING_DATA_DIR" \
VEHICLE_HOST='wheeltec@<orin-host>' \
./tools/mapping/sync_map_to_vehicle.sh floor1_mapping_001
```

同步脚本会在连接 Orin 前再次执行同一项 metadata 覆盖校验。校验失败的地图不会上传。

车端路径：

```text
~/Desktop/autoracer_hooke/maps/floor1_mapping_001
```

同步后按 `docs/operations/rc_runbook_zh.md` 先做 localization-only 验证，再启动完整
Autoware。车辆不在所选地图覆盖范围内时，不要求 NDT 收敛，也不能据此判断地图或
软件失败；必须回到对应现场完成初始位姿、定位、目标点和低速动态验证。
