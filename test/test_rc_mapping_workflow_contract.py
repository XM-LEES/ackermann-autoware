import json
import math
import os
import random
import struct
import subprocess
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_vehicle_mapping_scripts_exist_and_record_required_topics():
    record_script = ROOT / "scripts" / "record_mapping_bag.sh"
    check_script = ROOT / "scripts" / "check_mapping_inputs.sh"
    pull_script = ROOT / "scripts" / "pull_mapping_bag.sh"

    for script in (record_script, check_script, pull_script):
        assert script.exists(), f"missing mapping script: {script}"
        assert script.stat().st_mode & 0o111, f"script is not executable: {script}"

    record_text = record_script.read_text()
    for topic in (
        "/sensing/lidar/raw/pointcloud",
        "/sensing/lidar/concatenated/pointcloud",
        "/sensing/lidar/filtered/pointcloud",
        "/sensing/imu/imu_data_raw",
        "/sensing/imu/imu_data",
        "/tf",
        "/tf_static",
        "/rosout",
    ):
        assert topic in record_text
    assert "--include-unpublished-topics" in record_text
    assert "--polling-interval" in record_text
    assert "-e" in record_text

    check_text = check_script.read_text()
    stop_text = (ROOT / "scripts" / "rc" / "rc_stop.sh").read_text()
    assert "ring" in check_text
    assert "time" in check_text
    assert "return_type" in check_text
    assert "channel" in check_text
    assert "/sensing/lidar/raw/pointcloud" in check_text
    assert "/sensing/lidar/filtered/pointcloud" in check_text
    assert "/sensing/imu/imu_data" in check_text
    assert "c32_pointcloud_adapter" in stop_text

    rc_dir = ROOT / "scripts" / "rc"
    public_scripts = {
        "rc_configure_lidar.sh",
        "rc_start_sensors.sh",
        "rc_start_mapping_bag.sh",
        "rc_capture_mapping_bag.sh",
        "rc_stop_mapping_bag.sh",
        "rc_start_localization.sh",
        "rc_start_autoware.sh",
        "rc_stop.sh",
    }
    assert {path.name for path in rc_dir.glob("*.sh")} == public_scripts
    for script_name in public_scripts:
        assert (rc_dir / script_name).stat().st_mode & 0o111

    capture_text = (rc_dir / "rc_capture_mapping_bag.sh").read_text()
    assert "check_mapping_inputs.sh" in capture_text
    assert "record_mapping_bag.sh" in capture_text
    assert "rc_start_sensors.sh" in capture_text
    assert "kill -INT" in capture_text
    assert "ros2 bag info" in capture_text
    assert capture_text.count("scripts/ros_env.sh") >= 1
    assert "rc_start_mapping_bag.sh" in capture_text
    assert "run_track.sh" not in capture_text

    start_bag_text = (rc_dir / "rc_start_mapping_bag.sh").read_text()
    stop_bag_text = (rc_dir / "rc_stop_mapping_bag.sh").read_text()
    assert "check_mapping_inputs.sh" in start_bag_text
    assert "record_mapping_bag.sh" in start_bag_text
    assert "rc_start_sensors.sh" in start_bag_text
    assert "mapping_bag.env" in start_bag_text
    assert "run_track.sh" not in start_bag_text
    assert "kill -INT" in stop_bag_text
    assert "ros2 bag info" in stop_bag_text

    sensor_start_text = (rc_dir / "rc_start_sensors.sh").read_text()
    assert "run_official_autoware.sh" in sensor_start_text
    for setting in (
        "LAUNCH_MAP=false",
        "LAUNCH_LOCALIZATION=false",
        "LAUNCH_PLANNING=false",
        "LAUNCH_CONTROL=false",
        "LAUNCH_API=false",
        "LAUNCH_VEHICLE_INTERFACE=false",
    ):
        assert setting in sensor_start_text

    localization_start_text = (rc_dir / "rc_start_localization.sh").read_text()
    assert "run_official_autoware.sh" in localization_start_text
    assert "LAUNCH_PLANNING=false" in localization_start_text
    assert "LAUNCH_CONTROL=false" in localization_start_text
    assert 'LAUNCH_API="${LAUNCH_API:-true}"' in localization_start_text
    assert "LAUNCH_API=false" not in localization_start_text
    assert "LAUNCH_VEHICLE_INTERFACE=false" in localization_start_text
    stop_text = (rc_dir / "rc_stop.sh").read_text()
    assert "pkill" in stop_text
    assert "graceful_patterns" in stop_text
    assert "SHUTDOWN_GRACE_SEC" in stop_text
    assert "INTERRUPT_GRACE_SEC" in stop_text
    assert '${INTERRUPT_GRACE_SEC:-10}' in stop_text
    assert 'pkill -INT -u "${CURRENT_UID}" -f "${pattern}"' in stop_text
    assert 'pkill -TERM -u "${CURRENT_UID}" -f "${pattern}"' in stop_text
    assert "wait_for_patterns" in stop_text
    assert "traffic_reader" not in stop_text
    assert "component_container" in stop_text
    assert "topic_tools/relay" in stop_text
    assert "ROOT_DIR" in stop_text
    assert "/install/[a]utoware_" in stop_text


def test_rc_stop_waits_then_kills_a_process_that_ignores_term():
    stubborn = subprocess.Popen(
        [
            "bash",
            "-c",
            "trap '' TERM; exec -a c32_pointcloud_adapter sleep 60",
        ],
        start_new_session=True,
    )
    try:
        env = os.environ.copy()
        env.update({"SHUTDOWN_GRACE_SEC": "1", "STOP_WAIT_SEC": "1"})
        result = subprocess.run(
            ["bash", "scripts/rc/rc_stop.sh"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
        stubborn.wait(timeout=2)
    finally:
        if stubborn.poll() is None:
            stubborn.kill()
            stubborn.wait(timeout=2)

    assert result.returncode == 0, result.stderr
    assert "syntax error" not in result.stderr
    assert "[rc-stop] RC runtime processes stopped" in result.stdout


def test_script_layers_keep_rc_common_and_disabled_hooke_boundaries():
    common_readme = ROOT / "scripts" / "common" / "README.md"
    hooke_readme = ROOT / "scripts" / "hooke" / "README.md"
    hooke_start = ROOT / "scripts" / "hooke" / "hooke_start_autoware.sh"

    for path in (common_readme, hooke_readme, hooke_start):
        assert path.exists(), f"missing script boundary file: {path}"

    assert hooke_start.stat().st_mode & 0o111

    common_text = common_readme.read_text(encoding="utf-8")
    assert "shared helper layer" in common_text
    assert "must not encode RC or Hooke hardware facts" in common_text
    assert "scripts/rc/" in common_text
    assert "scripts/hooke/" in common_text

    hooke_text = "\n".join(
        (
            hooke_readme.read_text(encoding="utf-8"),
            hooke_start.read_text(encoding="utf-8"),
        )
    )
    assert "Hooke profile is disabled" in hooke_text
    assert "not runtime ready" in hooke_text
    assert "COLCON_IGNORE" in hooke_text
    assert "exit 2" in hooke_text
    assert "ros2 launch autoware_launch" not in hooke_start.read_text(encoding="utf-8")


def test_official_sensor_kit_exposes_hipnuc_imu_arguments():
    sensing_launch = (
        ROOT
        / "src"
        / "autoracer_rc_sensor_kit_launch"
        / "launch"
        / "sensing.launch.xml"
    )
    setup_py = ROOT / "src" / "autoracer_sensing" / "setup.py"

    sensing_text = sensing_launch.read_text()
    assert "launch_imu" in sensing_text
    assert "hipnuc_imu" in sensing_text
    assert "imu_filter_madgwick" in sensing_text
    assert "/sensing/imu/imu_data_raw" in sensing_text
    assert "/sensing/imu/imu_data" in sensing_text
    assert "c32_pointcloud_adapter" in sensing_text
    assert "/sensing/lidar/raw/pointcloud" in sensing_text
    assert "output_topic\" value=\"/sensing/lidar/concatenated/pointcloud" in sensing_text
    assert "pointcloud_voxel_filter" in sensing_text
    assert "c32_pointcloud_adapter" in setup_py.read_text()
    assert "pointcloud_voxel_filter" in setup_py.read_text()

    filter_text = (
        ROOT
        / "src"
        / "autoracer_sensing"
        / "autoracer_sensing"
        / "pointcloud_voxel_filter.py"
    ).read_text()
    assert "qos_profile_sensor_data" in filter_text


def test_official_branch_removes_legacy_track_entrypoints():
    removed_entrypoints = [
        ROOT / "scripts" / "run_track.sh",
        ROOT / "src" / "autoracer_bringup",
        ROOT / "src" / "autoracer_bringup" / "launch" / "track.launch.py",
        ROOT / "src" / "autoracer_bringup" / "launch" / "track_rc_p0.launch.py",
    ]
    for path in removed_entrypoints:
        assert not path.exists(), f"legacy formal entrypoint should be removed: {path}"

    run_official_text = (ROOT / "scripts" / "run_official_autoware.sh").read_text()
    for setting in (
        "LAUNCH_VEHICLE",
        "LAUNCH_SENSING",
        "LAUNCH_LOCALIZATION",
        "LAUNCH_PLANNING",
        "LAUNCH_CONTROL",
        "LAUNCH_API",
        "LAUNCH_VEHICLE_INTERFACE",
    ):
        assert setting in run_official_text
    assert "ros2 launch autoware_launch autoware.launch.xml" in run_official_text


def test_rc_serial_defaults_match_current_orin_chassis_port():
    defaults_text = (ROOT / "defaults.env").read_text()
    run_script_text = (ROOT / "scripts" / "run_official_autoware.sh").read_text()
    assert 'SERIAL_PORT:=/dev/ttyCH343USB0' in defaults_text
    assert 'IMU_SERIAL_PORT:=/dev/ttyUSB0' in defaults_text
    assert "SERIAL_PORT is required when LAUNCH_VEHICLE_INTERFACE=true" in run_script_text

    operator_files = [
        ROOT / "defaults.env",
        ROOT / "README.md",
        ROOT / "docs" / "operations" / "rc_runbook_zh.md",
        ROOT / "src" / "autoracer_rc_launch" / "launch" / "vehicle_interface.launch.xml",
        ROOT / "scripts" / "run_official_autoware.sh",
    ]
    for path in operator_files:
        assert "/dev/ttyACM0" not in path.read_text(), path


def test_rc_autoware_rviz_exposes_runtime_navigation_tools():
    rviz_path = (
        ROOT / "src" / "autoracer_rc_launch" / "rviz" / "rc_autoware.rviz"
    )
    rviz_text = rviz_path.read_text()
    rviz = yaml.safe_load(rviz_text)
    displays = {
        display["Name"]: display
        for display in rviz["Visualization Manager"]["Displays"]
    }

    for topic in (
        "/map/pointcloud_map",
        "/map/vector_map_marker",
        "/sensing/lidar/concatenated/pointcloud",
        "/sensing/lidar/filtered/pointcloud",
        "/points_aligned",
        "/localization/pose",
        "/localization/kinematic_state",
        "/vehicle/status/steering_status",
        "/vehicle/status/velocity_status",
        "/planning/mission_path",
        "/planning/mission_planning/route_marker",
        "/planning/mission_planning/goal",
        "/rviz/routing/rough_goal",
        "/initialpose",
    ):
        assert topic in rviz_text

    assert "rviz_default_plugins/SetInitialPose" in rviz_text
    assert "tier4_adapi_rviz_plugins::RouteTool" in rviz_text
    assert "rviz_default_plugins/Odometry" in rviz_text
    assert "rviz_plugins::AutowareStatePanel" in rviz_text
    assert "rviz_plugins/ControlModeDisplay" in rviz_text
    assert "rviz_plugins::PoseHistory" in rviz_text
    assert "rviz_plugins/SteeringAngle" in rviz_text
    assert "rviz_plugins/VelocityHistory" in rviz_text

    unavailable_or_simulation_only_plugins = (
        "rviz_plugins/PolarGridDisplay",
        "rviz_plugins/PedestrianInitialPoseTool",
        "rviz_plugins/CarInitialPoseTool",
        "rviz_plugins/BusInitialPoseTool",
        "rviz_plugins/DeleteAllObjectsTool",
    )
    for plugin in unavailable_or_simulation_only_plugins:
        assert plugin not in rviz_text

    assert "Hide Right Dock: true" in rviz_text
    assert "Height: 720" in rviz_text
    assert "Width: 1024" in rviz_text
    assert "Class: rviz_default_plugins/TopDownOrtho" in rviz_text
    assert "Target Frame: viewer" in rviz_text
    assert displays["PointCloud Map"]["Enabled"] is True
    assert displays["Lanelet2 Vector Map"]["Enabled"] is True
    assert displays["C32 Raw PointCloud"]["Enabled"] is False
    assert displays["C32 Raw PointCloud"]["Value"] is False
    assert displays["C32 Filtered PointCloud"]["Enabled"] is False
    assert displays["C32 Filtered PointCloud"]["Value"] is False
    assert displays["NDT Aligned PointCloud"]["Enabled"] is True


def test_mock_lidar_diagnostics_are_not_part_of_rc_flow():
    removed_paths = [
        ROOT / "src" / "autoracer_bringup" / "launch" / "mock_lidar_ndt.launch.py",
        ROOT / "src" / "autoracer_bringup" / "launch" / "mock_lidar_record_scenario.launch.py",
        ROOT / "src" / "autoracer_bringup" / "rviz" / "mock_lidar_ndt.rviz",
        ROOT / "src" / "autoracer_bringup" / "rviz" / "mock_lidar_record.rviz",
        ROOT / "src" / "autoracer_sensing" / "autoracer_sensing" / "mock_lidar_tools.py",
        ROOT / "src" / "autoracer_sensing" / "test" / "test_mock_lidar_tools.py",
    ]
    for path in removed_paths:
        assert not path.exists(), f"mock diagnostic file should stay removed: {path}"

    setup_text = (ROOT / "src" / "autoracer_sensing" / "setup.py").read_text()
    defaults_text = (ROOT / "defaults.env").read_text()
    assert "mock_lidar" not in setup_text
    assert "MOCK_LIDAR" not in defaults_text


def test_official_autoware_rviz_plugins_are_declared():
    repos_text = (ROOT / "autoracer.repos").read_text()
    import_script = (ROOT / "scripts" / "import_dependencies.sh").read_text()
    build_minimal = (ROOT / "scripts" / "build_minimal.sh").read_text()
    build_bench = (ROOT / "scripts" / "build_bench.sh").read_text()
    package_xml = (
        ROOT / "src" / "autoracer_rc_launch" / "package.xml"
    ).read_text()

    assert "autoware_rviz_plugins.git" in repos_text
    assert "src/autoware/autoware_rviz_plugins" in import_script
    assert "src/external/autoware/autoware_rviz_plugins" in import_script
    autoware_rviz_packages = (
        "autoware_localization_rviz_plugin",
        "autoware_planning_rviz_plugin",
    )
    tier4_rviz_packages = (
        "tier4_adapi_rviz_plugin",
        "tier4_control_mode_rviz_plugin",
        "tier4_state_rviz_plugin",
        "tier4_vehicle_rviz_plugin",
        "tier4_planning_factor_rviz_plugin",
    )

    for package in autoware_rviz_packages + tier4_rviz_packages:
        assert package in build_minimal
        assert package in build_bench
        assert package in package_xml

    for package in tier4_rviz_packages:
        assert package in import_script


def test_localization_parameters_come_from_official_autoware_launch():
    ndt_param = (
        ROOT
        / "src"
        / "external"
        / "autoware"
        / "launcher"
        / "autoware_launch"
        / "config"
        / "localization"
        / "ndt_scan_matcher"
        / "ndt_scan_matcher.param.yaml"
    )

    assert ndt_param.exists()
    ndt_text = ndt_param.read_text()
    assert 'base_frame: "base_link"' in ndt_text
    assert 'map_frame: "map"' in ndt_text
    assert "required_distance:" in ndt_text


def _rpy_matrix(roll, pitch, yaw):
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    return (
        (cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr),
        (sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr),
        (-sp, cp * sr, cp * cr),
    )


def _transpose(matrix):
    return tuple(zip(*matrix))


def _matmul(left, right):
    right_t = _transpose(right)
    return tuple(
        tuple(sum(a * b for a, b in zip(row, column)) for column in right_t)
        for row in left
    )


def test_mapping_tools_are_versioned_and_use_official_pointcloud_divider():
    mapping_dir = ROOT / "tools" / "mapping"
    expected = (
        mapping_dir / "mapping.repos",
        mapping_dir / "bootstrap_mapping_ws.sh",
        mapping_dir / "inspect_bag_topics.sh",
        mapping_dir / "audit_pointcloud_map.py",
        mapping_dir / "run_super_lio_offline.sh",
        mapping_dir / "prepare_autoware_pointcloud_map.sh",
        mapping_dir / "sync_map_to_vehicle.sh",
        mapping_dir / "validate_pointcloud_metadata.py",
        mapping_dir / "config" / "rc_c32_super_lio.yaml",
    )
    for path in expected:
        assert path.exists(), f"mapping workflow file is not versioned: {path}"
    for path in expected[1:8]:
        assert path.stat().st_mode & 0o111, f"mapping tool is not executable: {path}"

    repos = (mapping_dir / "mapping.repos").read_text(encoding="utf-8")
    assert "Super-LIO" in repos
    assert "autoware_tools" in repos
    assert "autoware_cmake" in repos
    assert "42a61372e02feaf656f84cdf3b5b793ff06d7ed4" in repos
    assert "2b5e7ed4c4a6e7a93f7aa4f46d6c75359c9e9b26" in repos
    assert "0e0794e034fe1b8fea6e3a0bbcb9d9b8cdba03ad" in repos

    prepare = (mapping_dir / "prepare_autoware_pointcloud_map.sh").read_text(
        encoding="utf-8"
    )
    assert "autoware_pointcloud_divider" in prepare
    assert "leaf_size" in prepare
    assert 'LEAF_SIZE="${LEAF_SIZE:--0.1}"' in prepare
    assert "grid_size_x" in prepare
    assert "grid_size_y" in prepare
    assert "pointcloud_map_metadata.yaml" in prepare
    assert "map_packager" not in prepare
    assert "audit_pointcloud_map.py" in prepare
    assert "quality_report.json" in prepare
    assert "validate_pointcloud_metadata.py" in prepare
    assert 'STAGING_DIR="$(mktemp -d' in prepare
    assert 'mv "${STAGING_DIR}" "${OUTPUT_DIR}"' in prepare

    sync = (mapping_dir / "sync_map_to_vehicle.sh").read_text(encoding="utf-8")
    assert "validate_pointcloud_metadata.py" in sync

    inspector = (mapping_dir / "inspect_bag_topics.sh").read_text(encoding="utf-8")
    assert "/sensing/lidar/raw/pointcloud" in inspector
    assert "/sensing/lidar/concatenated/pointcloud" in inspector
    assert "/sensing/imu/imu_data" in inspector
    assert "/imu/data" in inspector
    assert "full lidar time range" in inspector

    runner = (mapping_dir / "run_super_lio_offline.sh").read_text(encoding="utf-8")
    assert "super_lio_commit.txt" in runner
    assert "selected_topics.env" in runner
    assert "PLAYBACK_RATE" in runner
    assert "audit_pointcloud_map.py" in runner
    assert "quality_report.json" in runner

    docs = (ROOT / "docs" / "operations" / "mapping_workflow_zh.md").read_text(
        encoding="utf-8"
    )
    assert "tools/mapping" in docs
    assert "rc_mapping_tools.map_packager" not in docs
    assert "audit_pointcloud_map.py" in docs
    assert "LEAF_SIZE=-0.1" in docs
    assert "默认不额外降采样" in docs


def _write_synthetic_flat_road_pcd(path: Path, tilt_degrees: float) -> None:
    rng = random.Random(20260710)
    slope = math.tan(math.radians(tilt_degrees))
    points = []
    for _ in range(12000):
        x = rng.uniform(-30.0, 30.0)
        y = rng.uniform(-20.0, 20.0)
        z = slope * x + rng.gauss(0.0, 0.015)
        points.extend((x, y, z, rng.uniform(0.0, 255.0)))
    for _ in range(2000):
        points.extend(
            (
                rng.uniform(-30.0, 30.0),
                rng.uniform(-20.0, 20.0),
                rng.uniform(1.0, 8.0),
                rng.uniform(0.0, 255.0),
            )
        )

    point_count = len(points) // 4
    header = (
        "# .PCD v0.7 - Point Cloud Data file format\n"
        "VERSION 0.7\n"
        "FIELDS x y z intensity\n"
        "SIZE 4 4 4 4\n"
        "TYPE F F F F\n"
        "COUNT 1 1 1 1\n"
        f"WIDTH {point_count}\n"
        "HEIGHT 1\n"
        "VIEWPOINT 0 0 0 1 0 0 0\n"
        f"POINTS {point_count}\n"
        "DATA binary\n"
    ).encode("ascii")
    path.write_bytes(header + struct.pack(f"<{len(points)}f", *points))


def test_pointcloud_quality_gate_accepts_level_map_and_rejects_tilt(tmp_path):
    auditor = ROOT / "tools" / "mapping" / "audit_pointcloud_map.py"
    level_map = tmp_path / "level.pcd"
    tilted_map = tmp_path / "tilted.pcd"
    level_report = tmp_path / "level.json"
    tilted_report = tmp_path / "tilted.json"
    _write_synthetic_flat_road_pcd(level_map, tilt_degrees=1.0)
    _write_synthetic_flat_road_pcd(tilted_map, tilt_degrees=8.0)

    common_args = [
        "--iterations",
        "120",
        "--sample-size",
        "14000",
        "--max-ground-tilt-deg",
        "3.0",
    ]
    accepted = subprocess.run(
        [str(auditor), str(level_map), "--output", str(level_report), *common_args],
        text=True,
        capture_output=True,
        check=False,
    )
    rejected = subprocess.run(
        [str(auditor), str(tilted_map), "--output", str(tilted_report), *common_args],
        text=True,
        capture_output=True,
        check=False,
    )

    assert accepted.returncode == 0, accepted.stderr
    assert rejected.returncode == 2, rejected.stderr
    assert json.loads(level_report.read_text(encoding="utf-8"))["passed"] is True
    tilted = json.loads(tilted_report.read_text(encoding="utf-8"))
    assert tilted["passed"] is False
    assert tilted["ground_plane"]["tilt_degrees"] > 7.0


def test_super_lio_extrinsic_matches_rc_sensor_profile():
    calibration = yaml.safe_load(
        (
            ROOT
            / "src"
            / "autoracer_rc_sensor_kit_description"
            / "config"
            / "sensor_kit_calibration.yaml"
        ).read_text(encoding="utf-8")
    )["sensor_kit_base_link"]
    imu = calibration["imu_link"]
    lidar = calibration["lidar_top"]
    base_from_imu = _rpy_matrix(imu["roll"], imu["pitch"], imu["yaw"])
    base_from_lidar = _rpy_matrix(lidar["roll"], lidar["pitch"], lidar["yaw"])
    imu_from_lidar = _matmul(_transpose(base_from_imu), base_from_lidar)

    mapping_config = yaml.safe_load(
        (
            ROOT
            / "tools"
            / "mapping"
            / "config"
            / "rc_c32_super_lio.yaml"
        ).read_text(encoding="utf-8")
    )["/**"]["ros__parameters"]
    payload = mapping_config["lio.extrinsic.lidar_imu"]
    assert payload[:3] == [lidar["x"] - imu["x"], lidar["y"] - imu["y"], lidar["z"] - imu["z"]]

    # Super-LIO 42a6137 maps the flat payload through Eigen's default
    # column-major Matrix constructor. Reconstruct that consumed matrix here.
    flat_rotation = payload[3:]
    consumed = tuple(
        tuple(flat_rotation[row + 3 * column] for column in range(3))
        for row in range(3)
    )
    for actual_row, expected_row in zip(consumed, imu_from_lidar):
        for actual, expected in zip(actual_row, expected_row):
            assert math.isclose(actual, expected, abs_tol=2e-4)

    determinant = (
        consumed[0][0] * (consumed[1][1] * consumed[2][2] - consumed[1][2] * consumed[2][1])
        - consumed[0][1] * (consumed[1][0] * consumed[2][2] - consumed[1][2] * consumed[2][0])
        + consumed[0][2] * (consumed[1][0] * consumed[2][1] - consumed[1][1] * consumed[2][0])
    )
    assert math.isclose(determinant, 1.0, abs_tol=1e-5)
