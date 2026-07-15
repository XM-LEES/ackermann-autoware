# Autoracer

精简的 ROS 2 封闭赛道竞速栈。产品仓只版本化自研算法、薄平台适配、已验证资源和
依赖定义；Autoware 等第三方源码位于仓内可再生的 `vendor_ws` underlay，不混入产品源码树。

```text
Hooke2 / CarMaker / RC sensors
  -> pilot-compatible NDT + EKF localization
  -> validated fixed-course local trajectory
  -> Autoware MPC lateral + PID longitudinal control
  -> thin race runtime manager + Autoware vehicle command gate
  -> Hooke2 CAN / CarMaker Bridge / RC UART interface
```

## 目录边界

```text
autoracer_hooke/
  courses/                         已验证固定赛道轨迹
  maps/                            当前点云地图
  dependencies/                    固定源码目录、平台 profile 和最小补丁
  scripts/                         导入、构建、环境和硬件诊断脚本
  src/core/                        平台无关的定位、规划、控制和运行管理
  src/platform/hooke2/             Hooke2 CAN、车辆接口、消息和实车启动
  src/platform/rc/                 RC 传感、UART、车辆参数和薄启动组合
  vendor_ws/                       默认 Hooke 99 包的可再生 underlay（Git 忽略）
```

`src/core` 不依赖 CarMaker、Hooke2 或 RC 私有实现。两个平台共用同一套定位、规划、
控制和命令门控，仅在传感器输入、车辆执行与物理参数边界处切换平台适配。RC 的详细
接口见 `docs/rc_platform_contract.md`，上车前检查见 `docs/rc_bench_validation.md`。

## 依赖与构建

默认复用实车仓 `pilot-auto.x1` 中与版本锁一致的源码：

```bash
cd /opt/ipg/carmaker/linux64-15.1/autoracer_hooke
./scripts/import_dependencies.sh --refresh
./scripts/install_rosdeps.sh
./scripts/build.sh
source ./scripts/ros_env.sh
```

需要重新从实车仓同步依赖时：

```bash
./scripts/import_dependencies.sh --refresh
```

只有明确需要联网重建第三方工作区时才使用：

```bash
./scripts/import_dependencies.sh --network
```

`dependencies/autoracer.repos` 是上游 URL 和提交的唯一权威来源；
`dependencies/vendor-packages.tsv` 是 103 个可用包的目录；
`dependencies/profiles/` 分别选择 Hooke 和 RC 闭包。
`dependencies/patches/vehicle_cmd_gate_volatile_commands.patch` 是唯一产品所需上游补丁。

产品构建通过一个显式平台选择器复用同一源码图：

```bash
./scripts/build_product.sh
AUTORACER_PROFILE=rc \
AUTORACER_VENDOR_WS=/absolute/path/to/rc-vendor-ws \
./scripts/build_product.sh
```

默认 profile 为 `hooke2`。RC 必须显式选择 profile 和独立 vendor 工作区；不存在
`all` 模式。平台选择只改变依赖闭包和产品构建目标，不改变 core 源码或算法组合。

## 运行入口

- 仿真：双击桌面 `10km` 启动器，或运行
  `../SimProject_TianmenRace/run_pilot_localization_gui.sh`。该入口管理 CarMaker、Bridge、
  定位、规划、控制、运行管理、命令门控和 IPGMovie。
- 实车：

  ```bash
  ros2 launch autoracer_hooke2_bringup race.launch.py \
    localization_map_path:=/path/to/map \
    course_path:=/path/to/course
  ```

- RC（设备路径必须由当前机器提供）：

  ```bash
  ros2 launch autoracer_rc_bringup race.launch.py \
    localization_map_path:=/path/to/validated/rc/map \
    course_path:=/path/to/validated/rc/course \
    serial_port:=/dev/serial/by-id/rc-controller \
    imu_device:=/dev/serial/by-id/hipnuc-imu
  ```

RC 默认限速 `0.5 m/s`，且 `enable_drive_commands=false`。没有测量几何、传感器外参、
固件协议与低速闭环证据前，不得提高速度或打开驱动输出。

当前仿真资源为 `maps/urbanroad_route271_20260710` 和
`courses/urbanroad_route271_unlimited`。RViz 与硬件 smoke 脚本只用于诊断，不构成第二套运行栈。
