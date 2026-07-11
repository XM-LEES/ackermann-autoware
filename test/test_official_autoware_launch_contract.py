import math
import os
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def package_name(package_xml: Path) -> str:
    tree = ET.parse(package_xml)
    name = tree.getroot().findtext("name")
    assert name
    return name


def test_autoware_launch_is_pinned_as_the_official_entrypoint():
    repos = read("autoracer.repos")

    assert "src/external/autoware/launcher" in repos
    assert "https://github.com/autowarefoundation/autoware_launch.git" in repos
    assert "version: 0.50.0" in repos


def test_autoracer_vehicle_and_sensor_kit_packages_follow_official_names():
    expected_packages = {
        "src/autoracer_rc_description/package.xml": "autoracer_rc_description",
        "src/autoracer_rc_launch/package.xml": "autoracer_rc_launch",
        "src/autoracer_rc_sensor_kit_description/package.xml": (
            "autoracer_rc_sensor_kit_description"
        ),
        "src/autoracer_rc_sensor_kit_launch/package.xml": (
            "autoracer_rc_sensor_kit_launch"
        ),
    }

    for relative_path, expected_name in expected_packages.items():
        package_xml = ROOT / relative_path
        assert package_xml.exists(), f"missing package.xml: {relative_path}"
        assert package_name(package_xml) == expected_name

    assert "autoracer_bringup" not in read("src/autoracer_rc_launch/package.xml")
    assert "autoracer_bringup" not in read("src/autoracer_rc_sensor_kit_launch/package.xml")


def test_hooke_profile_placeholders_are_disabled_until_real_profile_exists():
    expected_placeholders = {
        "src/autoracer_hooke_description": [
            "vehicle_info.param.yaml",
            "vehicle.xacro",
            "real Hooke vehicle geometry",
        ],
        "src/autoracer_hooke_launch": [
            "vehicle_interface.launch.xml",
            "Hooke CAN adapter",
            "command gate",
        ],
        "src/autoracer_hooke_sensor_kit_description": [
            "sensor_kit_calibration.yaml",
            "sensors_calibration.yaml",
            "real Hooke sensor extrinsics",
        ],
        "src/autoracer_hooke_sensor_kit_launch": [
            "sensing.launch.xml",
            "Hesai",
            "Fixposition",
        ],
    }

    for relative_path, required_terms in expected_placeholders.items():
        placeholder = ROOT / relative_path
        assert placeholder.is_dir(), f"missing Hooke placeholder: {relative_path}"
        assert (placeholder / "COLCON_IGNORE").exists()
        assert not (placeholder / "package.xml").exists()
        assert (placeholder / "README.md").exists()
        assert (placeholder / "profile_requirements.yaml").exists()

        combined = "\n".join(
            (
                (placeholder / "README.md").read_text(encoding="utf-8"),
                (placeholder / "profile_requirements.yaml").read_text(encoding="utf-8"),
            )
        )
        for term in (
            "disabled_placeholder",
            "not runtime ready",
            "Remove COLCON_IGNORE only after",
            "autoracer_hooke",
            "autoracer_hooke_sensor_kit",
            *required_terms,
        ):
            assert term in combined, f"{term!r} missing from {relative_path}"


def test_official_launch_packages_expose_expected_launch_files_and_rc_hardware():
    vehicle_launch = ROOT / "src" / "autoracer_rc_launch" / "launch" / "vehicle_interface.launch.xml"
    sensing_launch = (
        ROOT
        / "src"
        / "autoracer_rc_sensor_kit_launch"
        / "launch"
        / "sensing.launch.xml"
    )
    lidar_config = (
        ROOT / "src" / "autoracer_rc_sensor_kit_launch" / "config" / "lslidar_cx.yaml"
    )
    vehicle_info = (
        ROOT
        / "src"
        / "autoracer_rc_description"
        / "config"
        / "vehicle_info.param.yaml"
    )
    sensor_calibration = (
        ROOT
        / "src"
        / "autoracer_rc_sensor_kit_description"
        / "config"
        / "sensor_kit_calibration.yaml"
    )

    for path in (vehicle_launch, sensing_launch, lidar_config, vehicle_info, sensor_calibration):
        assert path.exists(), f"missing official Autoware integration file: {path}"

    vehicle_text = vehicle_launch.read_text(encoding="utf-8")
    assert "autoracer_vehicle_interface" in vehicle_text
    assert "rc_serial_interface" in vehicle_text
    assert "autoracer_safety" in vehicle_text
    assert "command_gate" in vehicle_text
    assert "vehicle_velocity_converter" in vehicle_text
    assert "ENABLE_DRIVE_COMMANDS" in vehicle_text
    assert "/autoracer/control/safe_control_cmd" in vehicle_text
    assert "/sensing/vehicle_velocity_converter/twist_with_covariance" in vehicle_text
    assert "/dev/ttyUSB0" not in vehicle_text

    sensing_text = sensing_launch.read_text(encoding="utf-8")
    for term in (
        "lslidar_driver",
        "hipnuc_imu",
        "c32_pointcloud_adapter",
        "pointcloud_voxel_filter",
        "/dev/ttyUSB0",
        "lslidar_cx.yaml",
        "/sensing/lidar/raw/pointcloud",
        "/sensing/lidar/concatenated/pointcloud",
        "/sensing/imu/imu_data_raw",
        "/sensing/imu/imu_data",
    ):
        assert term in sensing_text
    assert '<group if="$(var launch_driver)">' in sensing_text

    lidar_config_text = lidar_config.read_text(encoding="utf-8")
    assert "device_ip: 192.168.1.200" in lidar_config_text
    assert "192.168.1.200" in lidar_config_text

    calibration = yaml.safe_load(sensor_calibration.read_text(encoding="utf-8"))[
        "sensor_kit_base_link"
    ]
    assert math.isclose(calibration["lidar_top"]["yaw"], -math.pi / 2, abs_tol=0.01)
    assert abs(calibration["lidar_top"]["roll"]) > 0.01
    assert abs(calibration["imu_link"]["pitch"]) > 0.01


def test_operator_docs_prefer_official_autoware_launch_command():
    readme = read("README.md")
    rc_start = read("scripts/rc/rc_start_autoware.sh")
    run_official = read("scripts/run_official_autoware.sh")

    assert "ros2 launch autoware_launch autoware.launch.xml" in readme
    assert "vehicle_model:=autoracer_rc" in readme
    assert "sensor_model:=autoracer_rc_sensor_kit" in readme
    assert "launch_perception:=false" in readme
    assert "rviz:=false" in readme
    assert "launch_vehicle_interface:=false" in readme
    assert "run_official_autoware.sh" in rc_start
    assert "ros2 launch autoware_launch autoware.launch.xml" in run_official
    assert "exec ros2 launch autoware_launch autoware.launch.xml" in run_official
    assert "AUTORACER_VEHICLE_MODEL:=autoracer_rc" in run_official
    assert "AUTORACER_SENSOR_MODEL:=autoracer_rc_sensor_kit" in run_official
    assert "Only the RC official profile is enabled in this branch" in run_official
    assert "require_active_profile_pair" in run_official
    assert "disabled_placeholder" in run_official
    assert 'vehicle_model:="${AUTORACER_VEHICLE_MODEL}"' in run_official
    assert 'sensor_model:="${AUTORACER_SENSOR_MODEL}"' in run_official
    assert 'launch_perception:="${LAUNCH_PERCEPTION}"' in run_official
    assert 'rviz_config:="${RVIZ_CONFIG}"' in run_official
    assert "autoracer_rc_launch/rviz/rc_autoware.rviz" in run_official
    assert "SERIAL_PORT is required when LAUNCH_VEHICLE_INTERFACE=true" in run_official


def test_official_wrapper_rejects_disabled_hooke_profile_before_ros_launch():
    env = os.environ.copy()
    env.update(
        {
            "AUTORACER_VEHICLE_MODEL": "autoracer_hooke",
            "AUTORACER_SENSOR_MODEL": "autoracer_hooke_sensor_kit",
            "MAP_PATH": str(ROOT / "maps"),
            "LAUNCH_VEHICLE_INTERFACE": "false",
            "RC_REQUIRE_LIDAR_LINK": "false",
        }
    )

    result = subprocess.run(
        ["bash", "scripts/run_official_autoware.sh"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )

    assert result.returncode == 2
    assert "Only the RC official profile is enabled in this branch" in result.stderr
    assert "Requested vehicle_model=autoracer_hooke" in result.stderr
    assert "disabled_placeholder" in result.stderr
    assert "ros2 launch" not in result.stderr


def test_official_wrapper_preflights_complete_map_and_accepts_full_or_tiled_pcd():
    run_official = read("scripts/run_official_autoware.sh")

    assert "require_map_assets" in run_official
    assert "pointcloud_map_metadata.yaml" in run_official
    assert "lanelet2_map.osm" in run_official
    assert "map_projector_info.yaml" in run_official
    assert "-d \"${pointcloud_path}\"" in run_official
    assert "find \"${pointcloud_path}\" -type f -name '*.pcd'" in run_official
    assert 'MAX_SINGLE_PCD_BYTES:-0' in run_official
    assert "max_single_pcd_bytes > 0" in run_official


def test_official_wrapper_supplies_orin_display_for_ssh_started_rviz():
    run_official = read("scripts/run_official_autoware.sh")

    assert "RVIZ_DISPLAY" in run_official
    assert "RVIZ_XAUTHORITY" in run_official
    assert 'export DISPLAY="${RVIZ_DISPLAY}"' in run_official
    assert 'export XAUTHORITY="${RVIZ_XAUTHORITY}"' in run_official


def test_system_monitor_traffic_reader_has_a_reproducible_host_service():
    installer_path = ROOT / "tools" / "system" / "install_traffic_reader_service.sh"
    unit_path = ROOT / "tools" / "system" / "autoracer-traffic-reader.service.in"

    assert installer_path.exists()
    assert installer_path.stat().st_mode & 0o111
    assert unit_path.exists()

    installer = installer_path.read_text(encoding="utf-8")
    unit = unit_path.read_text(encoding="utf-8")

    assert "nethogs" in installer
    assert "ros2 pkg prefix autoware_system_monitor" in installer
    assert "systemctl daemon-reload" in installer
    assert 'systemctl enable --now "${UNIT_NAME}"' in installer
    assert "test -S /tmp/traffic_reader" in installer

    assert "Type=forking" in unit
    assert "@TRAFFIC_READER_BINARY@" in unit
    assert "ExecStartPre=-/usr/bin/pkill -x traffic_reader" in unit
    assert "ExecStartPre=/usr/bin/rm -f /tmp/traffic_reader" in unit
    assert "WantedBy=multi-user.target" in unit


def test_onboard_host_setup_applies_official_cyclonedds_tuning():
    configurator_path = ROOT / "tools" / "system" / "configure_onboard_host.sh"
    sysctl_path = ROOT / "tools" / "system" / "autoracer-dds.conf"
    cyclone_path = ROOT / "config" / "middleware" / "cyclonedds.xml"

    assert configurator_path.exists()
    assert configurator_path.stat().st_mode & 0o111
    assert sysctl_path.exists()
    assert cyclone_path.exists()

    configurator = configurator_path.read_text(encoding="utf-8")
    sysctl_config = sysctl_path.read_text(encoding="utf-8")
    cyclone_config = cyclone_path.read_text(encoding="utf-8")
    ros_env = read("scripts/ros_env.sh")

    assert "install_traffic_reader_service.sh" in configurator
    assert "/etc/sysctl.d/60-autoracer-dds.conf" in configurator
    assert 'sysctl -p "${SYSCTL_PATH}"' in configurator
    assert "ip link set dev lo multicast on" in configurator
    assert "net.core.rmem_max=2147483647" in sysctl_config
    assert "net.core.rmem_default=134217728" in sysctl_config
    assert "net.ipv4.ipfrag_time=3" in sysctl_config
    assert "net.ipv4.ipfrag_high_thresh=134217728" in sysctl_config
    assert 'name="lo"' in cyclone_config
    assert '<SocketReceiveBufferSize min="10MB"/>' in cyclone_config
    assert "<MaxMessageSize>65500B</MaxMessageSize>" in cyclone_config
    assert "CYCLONEDDS_URI" in ros_env
    assert "config/middleware/cyclonedds.xml" in ros_env


def test_rc_profile_supplies_system_monitor_network_interfaces():
    net_config_path = (
        ROOT
        / "src"
        / "autoracer_rc_launch"
        / "config"
        / "system_monitor"
        / "net_monitor.param.yaml"
    )
    assert net_config_path.exists()
    net_config = yaml.safe_load(net_config_path.read_text(encoding="utf-8"))["/**"][
        "ros__parameters"
    ]
    assert net_config["devices"] == ["enP8p1s0"]
    assert net_config["monitor_program"] == ""
    assert net_config["enable_traffic_monitor"] is True

    cmake = read("src/autoracer_rc_launch/CMakeLists.txt")
    wrapper = read("scripts/run_official_autoware.sh")
    top_level = read(
        "src/external/autoware/launcher/autoware_launch/launch/autoware.launch.xml"
    )
    system_component = read(
        "src/external/autoware/launcher/autoware_launch/launch/components/"
        "tier4_system_component.launch.xml"
    )

    assert "install(DIRECTORY launch rviz config" in cmake
    assert "SYSTEM_MONITOR_NET_PARAM_PATH" in wrapper
    assert 'system_monitor_net_monitor_param_path:="${SYSTEM_MONITOR_NET_PARAM_PATH}"' in wrapper
    assert 'name="system_monitor_net_monitor_param_path"' in top_level
    assert '<arg name="system_monitor_net_monitor_param_path" value="$(var system_monitor_net_monitor_param_path)"/>' in top_level
    assert 'name="system_monitor_net_monitor_param_path"' in system_component
    assert '<arg name="system_monitor_net_monitor_param_path" value="$(var system_monitor_net_monitor_param_path)"/>' in system_component


def test_official_localization_contract_uses_upstream_default_pointcloud_topic():
    top_level_launch = read(
        "src/external/autoware/launcher/autoware_launch/launch/autoware.launch.xml"
    )
    localization_component = read(
        "src/external/autoware/launcher/autoware_launch/launch/components/tier4_localization_component.launch.xml"
    )
    tier4_localization = read(
        "src/external/autoware/launcher/tier4_universe_launch/tier4_localization_launch/launch/localization.launch.xml"
    )
    run_official = read("scripts/run_official_autoware.sh")
    ros_env = read("scripts/ros_env.sh")
    docs = "\n".join(
        read(path)
        for path in (
            "docs/architecture_zh.md",
            "docs/reference/interfaces_and_calibration_zh.md",
        )
    )

    assert 'name="input_pointcloud" default="/sensing/lidar/concatenated/pointcloud"' in localization_component
    assert 'name="gnss_enabled" default="true"' in top_level_launch
    assert '<arg name="gnss_enabled" value="$(var gnss_enabled)"/>' in top_level_launch
    assert 'name="gnss_enabled" default="true"' in localization_component
    assert 'name="gnss_enabled" default="true"' in tier4_localization
    assert 'gnss_enabled:="${GNSS_ENABLED}"' in run_official
    assert 'GNSS_ENABLED:=false' in run_official
    assert "rmw_cyclonedds_cpp" in ros_env
    assert "AUTORACER_DEFAULT_RMW" in ros_env
    assert "official localization 默认消费 `/sensing/lidar/concatenated/pointcloud`" in docs
    assert "runtime localization consumes the official default concatenated topic" in docs


def test_official_localization_docs_require_full_map_directory():
    docs = "\n".join(
        read(path)
        for path in (
            "README.md",
            "docs/operations/mapping_workflow_zh.md",
            "docs/operations/rc_runbook_zh.md",
            "docs/reference/interfaces_and_calibration_zh.md",
        )
    )

    assert "pointcloud_map.pcd" in docs
    assert "pointcloud_map_metadata.yaml" in docs
    assert "lanelet2_map.osm" in docs
    assert "map_projector_info.yaml" in docs
    assert "PCD-only" not in docs
    assert "只有 PCD" not in docs
    assert "没有 Lanelet2 地图时只验证 localization-only" not in docs


def test_official_branch_operator_entrypoints_do_not_call_legacy_track_launcher():
    entrypoint_files = [
        "scripts/rc/rc_start_autoware.sh",
        "scripts/rc/rc_start_sensors.sh",
        "scripts/rc/rc_start_mapping_bag.sh",
        "scripts/rc/rc_capture_mapping_bag.sh",
        "scripts/rc/rc_start_localization.sh",
        "scripts/rc/rc_stop.sh",
    ]

    for relative_path in entrypoint_files:
        text = read(relative_path)
        assert "run_track.sh" not in text, relative_path
        assert "autoracer_bringup track.launch.py" not in text, relative_path
        assert "track_rc_p0.launch.py" not in text, relative_path

    assert not (ROOT / "scripts" / "run_track.sh").exists()
    assert not (
        ROOT / "src" / "autoracer_bringup" / "launch" / "track.launch.py"
    ).exists()
    assert not (
        ROOT / "src" / "autoracer_bringup" / "launch" / "track_rc_p0.launch.py"
    ).exists()
