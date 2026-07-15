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

from pathlib import Path
import math

import yaml


RC_ROOT = Path(__file__).resolve().parents[2]
DESCRIPTION = RC_ROOT / "autoracer_rc_description"
BRINGUP = RC_ROOT / "autoracer_rc_bringup"


def load_yaml(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_vehicle_reference_geometry_is_explicit_and_safe():
    data = load_yaml(DESCRIPTION / "config/vehicle_info.param.yaml")
    params = data["/**"]["ros__parameters"]
    assert params["wheel_radius"] == 0.115
    assert params["wheel_base"] == 0.600
    assert params["wheel_tread"] == 0.470
    assert params["max_steer_angle"] == 0.262
    for name, value in params.items():
        assert math.isfinite(value), name
        assert value > 0.0, name
    assert 0.0 < params["max_steer_angle"] < math.pi / 2.0


def test_extrinsics_define_each_rc_sensor_once():
    data = load_yaml(DESCRIPTION / "config/sensor_extrinsics.yaml")
    transforms = data["transforms"]
    assert [(item["parent"], item["child"]) for item in transforms] == [
        ("base_link", "lidar_top"),
        ("base_link", "imu_link"),
    ]
    for item in transforms:
        values = list(item["translation"].values()) + list(item["rotation_rpy"].values())
        assert all(math.isfinite(value) for value in values)


def test_lidar_runtime_profile_matches_the_profile_used_to_build_rc_maps():
    lidar = load_yaml(BRINGUP / "config/rc/lidar.param.yaml")[
        "/cx/lslidar_driver_node"
    ]["ros__parameters"]
    assert lidar["coordinate_opt"] is False
    assert lidar["angle_disable_min"] == 11000
    assert lidar["angle_disable_max"] == 25000

    extrinsics = load_yaml(DESCRIPTION / "config/sensor_extrinsics.yaml")["transforms"]
    lidar_tf = next(item for item in extrinsics if item["child"] == "lidar_top")
    assert lidar_tf["translation"] == {"x": 0.24, "y": 0.0, "z": 0.39}
    assert lidar_tf["rotation_rpy"] == {
        "roll": -0.081569052095,
        "pitch": -0.023125019399,
        "yaw": -1.569852618571,
    }


def test_static_tf_launch_reads_the_single_extrinsics_file():
    source = (DESCRIPTION / "launch/static_tf.launch.py").read_text(encoding="utf-8")
    assert "sensor_extrinsics.yaml" in source
    assert "yaml.safe_load" in source
    assert "static_transform_publisher" in source


def test_urdf_does_not_duplicate_extrinsic_numbers():
    source = (DESCRIPTION / "urdf/rc_sensor_mounts.urdf.xacro").read_text(encoding="utf-8")
    for frame in ("base_link", "lidar_top", "imu_link"):
        assert f'name="{frame}"' in source
    assert "<origin" not in source


def test_rc_overlays_never_exceed_physical_or_initial_safety_limits():
    vehicle = load_yaml(DESCRIPTION / "config/vehicle_info.param.yaml")["/**"][
        "ros__parameters"
    ]
    gate = load_yaml(BRINGUP / "config/rc/vehicle_cmd_gate.param.yaml")["/**"][
        "ros__parameters"
    ]
    runtime = load_yaml(BRINGUP / "config/rc/race_runtime.param.yaml")[
        "race_runtime_manager"
    ]["ros__parameters"]
    assert gate["nominal"]["vel_lim"] <= 0.5
    assert gate["on_transition"]["vel_lim"] <= 0.5
    for mode in ("nominal", "on_transition"):
        assert max(gate[mode]["steer_cmd_lim"]) <= vehicle["max_steer_angle"]
    assert runtime["vehicle_status_timeout_sec"] <= 0.5
    assert runtime["emergency_acceleration_mps2"] <= -0.8
    overlay_source = "\n".join(
        path.read_text(encoding="utf-8") for path in (BRINGUP / "config/rc").glob("*.yaml")
    )
    assert "100.0" not in overlay_source
