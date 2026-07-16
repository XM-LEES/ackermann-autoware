# Copyright 2026 OpenAI
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
from pathlib import Path
import subprocess


PACKAGE = Path(__file__).resolve().parents[1]
ENTRYPOINT = PACKAGE / "scripts" / "start_rc_race.sh"


def test_quickstart_is_owned_by_the_rc_platform_and_fail_closed():
    source = ENTRYPOINT.read_text(encoding="utf-8")

    assert "autoracer_rc_bringup race.launch.py" in source
    assert 'enable_drive_commands:=false' in source
    assert 'launch_rviz:="${RC_LAUNCH_RVIZ:-true}"' in source
    for required in (
        "RC_REPO_ROOT",
        "RC_VENDOR_WS",
        "RC_PRODUCT_WS",
        "RC_MAP_ROOT",
        "RC_SERIAL_PORT",
        "RC_IMU_DEVICE",
        "map_manifest.json",
        "courses/rc",
    ):
        assert required in source
    for forbidden in (
        "Desktop/autoracer_hooke",
        "/home/wheeltec/autoware",
        "autoware_launch",
        "request_autonomous_mode",
        "ENABLE_DRIVE_COMMANDS=true",
        "safe_control_cmd",
    ):
        assert forbidden not in source


def test_quickstart_launches_only_after_explicit_assets_and_devices_exist(tmp_path):
    repo = tmp_path / "product"
    map_root = tmp_path / "maps"
    vendor = tmp_path / "rc-vendor"
    product = tmp_path / "rc-product"
    ros_setup = tmp_path / "ros-setup.bash"
    fake_bin = tmp_path / "bin"
    map_id = "floor1_mapping_101"
    for path in (
        repo / "src/platform/rc/autoracer_rc_bringup/launch",
        repo / "courses/rc" / map_id,
        map_root / map_id,
        vendor / "install",
        product / "install",
        fake_bin,
    ):
        path.mkdir(parents=True, exist_ok=True)
    (repo / "src/platform/rc/autoracer_rc_bringup/launch/race.launch.py").touch()
    (repo / "courses/rc" / map_id / "manifest.json").write_text("{}\n")
    (map_root / map_id / "map_manifest.json").write_text("{}\n")
    (vendor / "install/local_setup.bash").write_text("")
    (product / "install/local_setup.bash").write_text("")
    ros_setup.write_text("")
    serial = tmp_path / "rc-serial"
    imu = tmp_path / "imu-serial"
    serial.touch()
    imu.touch()
    ros2 = fake_bin / "ros2"
    ros2.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$*"\n')
    ros2.chmod(0o755)

    environment = os.environ.copy()
    environment.update(
        {
            "PATH": f"{fake_bin}:{environment['PATH']}",
            "RC_REPO_ROOT": str(repo),
            "RC_VENDOR_WS": str(vendor),
            "RC_PRODUCT_WS": str(product),
            "RC_ROS_SETUP": str(ros_setup),
            "RC_MAP_ROOT": str(map_root),
            "RC_SERIAL_PORT": str(serial),
            "RC_IMU_DEVICE": str(imu),
        }
    )
    result = subprocess.run(
        [str(ENTRYPOINT), map_id],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert "launch autoracer_rc_bringup race.launch.py" in result.stdout
    assert f"localization_map_path:={map_root / map_id}" in result.stdout
    assert f"course_path:={repo / 'courses/rc' / map_id}" in result.stdout
    assert f"serial_port:={serial}" in result.stdout
    assert f"imu_device:={imu}" in result.stdout
    assert "enable_drive_commands:=false" in result.stdout
    assert "launch_rviz:=true" in result.stdout


def test_quickstart_rejects_an_unprepared_repository(tmp_path):
    environment = os.environ.copy()
    environment.update(
        {
            "RC_REPO_ROOT": str(tmp_path / "legacy"),
            "RC_VENDOR_WS": str(tmp_path / "rc-vendor"),
            "RC_PRODUCT_WS": str(tmp_path / "rc-product"),
            "RC_MAP_ROOT": str(tmp_path / "maps"),
            "RC_SERIAL_PORT": str(tmp_path / "serial"),
            "RC_IMU_DEVICE": str(tmp_path / "imu"),
        }
    )
    result = subprocess.run(
        [str(ENTRYPOINT), "floor1_mapping_101"],
        capture_output=True,
        text=True,
        env=environment,
    )

    assert result.returncode == 2
    assert "new RC product repository" in result.stderr
