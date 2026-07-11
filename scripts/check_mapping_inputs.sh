#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

usage() {
  cat <<'EOF'
Usage:
  check_mapping_inputs.sh

Environment:
  RAW_LIDAR_TOPIC               default: /sensing/lidar/raw/pointcloud
  LIDAR_TOPIC                   default: /sensing/lidar/concatenated/pointcloud
  FILTERED_LIDAR_TOPIC          default: /sensing/lidar/filtered/pointcloud
  IMU_RAW_TOPIC                 default: /sensing/imu/imu_data_raw
  IMU_TOPIC                     default: /sensing/imu/imu_data
  TF_STATIC_TOPIC               default: /tf_static
  TOPIC_DISCOVERY_TIMEOUT_SEC   default: 20
  CHECK_TIMEOUT_SEC             default: 8

Checks live RC mapping inputs: raw C32 PointCloud2 fields, Autoware-adapted
PointXYZIRC fields, Hipnuc raw/filtered IMU, and static TF.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -gt 0 ]]; then
  echo "ERROR: unknown argument: $1" >&2
  usage >&2
  exit 1
fi

# shellcheck disable=SC1091
source "${ROOT_DIR}/scripts/ros_env.sh"

CHECK_TIMEOUT_SEC="${CHECK_TIMEOUT_SEC:-8}"
TOPIC_DISCOVERY_TIMEOUT_SEC="${TOPIC_DISCOVERY_TIMEOUT_SEC:-20}"
RAW_LIDAR_TOPIC="${RAW_LIDAR_TOPIC:-/sensing/lidar/raw/pointcloud}"
LIDAR_TOPIC="${LIDAR_TOPIC:-/sensing/lidar/concatenated/pointcloud}"
FILTERED_LIDAR_TOPIC="${FILTERED_LIDAR_TOPIC:-/sensing/lidar/filtered/pointcloud}"
IMU_RAW_TOPIC="${IMU_RAW_TOPIC:-/sensing/imu/imu_data_raw}"
IMU_TOPIC="${IMU_TOPIC:-/sensing/imu/imu_data}"
TF_STATIC_TOPIC="${TF_STATIC_TOPIC:-/tf_static}"

export CHECK_TIMEOUT_SEC
export TOPIC_DISCOVERY_TIMEOUT_SEC
export RAW_LIDAR_TOPIC
export LIDAR_TOPIC
export FILTERED_LIDAR_TOPIC
export IMU_RAW_TOPIC
export IMU_TOPIC
export TF_STATIC_TOPIC

python3 - <<'PY'
import os
import sys
import time

import rclpy
from rclpy.qos import DurabilityPolicy, QoSProfile
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Imu, PointCloud2, PointField
from tf2_msgs.msg import TFMessage


check_timeout = float(os.environ["CHECK_TIMEOUT_SEC"])
discovery_timeout = float(os.environ["TOPIC_DISCOVERY_TIMEOUT_SEC"])
lidar_topic = os.environ["LIDAR_TOPIC"]
raw_lidar_topic = os.environ["RAW_LIDAR_TOPIC"]
filtered_lidar_topic = os.environ["FILTERED_LIDAR_TOPIC"]
imu_raw_topic = os.environ["IMU_RAW_TOPIC"]
imu_topic = os.environ["IMU_TOPIC"]
tf_static_topic = os.environ["TF_STATIC_TOPIC"]

counts = {
    raw_lidar_topic: 0,
    lidar_topic: 0,
    filtered_lidar_topic: 0,
    imu_raw_topic: 0,
    imu_topic: 0,
    tf_static_topic: 0,
}
first_stamp = {}
last_stamp = {}
pointcloud_fields = {}


def mark(topic):
    now = time.monotonic()
    counts[topic] += 1
    first_stamp.setdefault(topic, now)
    last_stamp[topic] = now


def make_pointcloud_callback(topic):
    def on_pointcloud(msg):
        mark(topic)
        if topic not in pointcloud_fields:
            pointcloud_fields[topic] = [
                (field.name, field.offset, field.datatype, field.count) for field in msg.fields
            ]

    return on_pointcloud


def on_filtered_pointcloud(_msg):
    mark(filtered_lidar_topic)


def on_imu_raw(_msg):
    mark(imu_raw_topic)


def on_imu(_msg):
    mark(imu_topic)


def on_tf_static(_msg):
    mark(tf_static_topic)


rclpy.init()
node = rclpy.create_node("rc_mapping_input_check")
tf_static_qos = QoSProfile(depth=1)
tf_static_qos.durability = DurabilityPolicy.TRANSIENT_LOCAL

node.create_subscription(PointCloud2, raw_lidar_topic, make_pointcloud_callback(raw_lidar_topic), qos_profile_sensor_data)
node.create_subscription(PointCloud2, lidar_topic, make_pointcloud_callback(lidar_topic), qos_profile_sensor_data)
node.create_subscription(
    PointCloud2, filtered_lidar_topic, on_filtered_pointcloud, qos_profile_sensor_data
)
node.create_subscription(Imu, imu_raw_topic, on_imu_raw, qos_profile_sensor_data)
node.create_subscription(Imu, imu_topic, on_imu, qos_profile_sensor_data)
node.create_subscription(TFMessage, tf_static_topic, on_tf_static, tf_static_qos)

deadline = time.monotonic() + discovery_timeout
while time.monotonic() < deadline:
    rclpy.spin_once(node, timeout_sec=0.2)
    if all(counts[topic] > 0 for topic in counts):
        break

sample_deadline = time.monotonic() + check_timeout
while time.monotonic() < sample_deadline:
    rclpy.spin_once(node, timeout_sec=0.2)

failures = 0
for topic in (raw_lidar_topic, lidar_topic, filtered_lidar_topic, imu_raw_topic, imu_topic, tf_static_topic):
    if counts[topic] > 0:
        print(f"[mapping-check] OK topic data: {topic} ({counts[topic]} msg)")
    else:
        print(f"[mapping-check] FAIL: missing data: {topic}", file=sys.stderr)
        failures += 1

def require_field_names(topic, required_fields, label):
    global failures
    fields = pointcloud_fields.get(topic)
    if fields is None:
        print(f"[mapping-check] FAIL: failed to read PointCloud2 fields from {topic}", file=sys.stderr)
        failures += 1
        return
    names = {field[0] for field in fields}
    missing = sorted(set(required_fields).difference(names))
    if missing:
        print(
            f"[mapping-check] FAIL: {topic} missing {label} fields: {', '.join(missing)}",
            file=sys.stderr,
        )
        failures += 1
    else:
        print(f"[mapping-check] OK {label} fields: {' '.join(required_fields)}")


def require_autoware_xyzirc_layout(topic):
    global failures
    fields = pointcloud_fields.get(topic)
    expected = [
        ("x", 0, PointField.FLOAT32, 1),
        ("y", 4, PointField.FLOAT32, 1),
        ("z", 8, PointField.FLOAT32, 1),
        ("intensity", 12, PointField.UINT8, 1),
        ("return_type", 13, PointField.UINT8, 1),
        ("channel", 14, PointField.UINT16, 1),
    ]
    if fields is None:
        print(f"[mapping-check] FAIL: failed to read PointCloud2 fields from {topic}", file=sys.stderr)
        failures += 1
        return
    if fields[: len(expected)] != expected:
        print(
            f"[mapping-check] FAIL: {topic} is not Autoware PointXYZIRC layout: {fields}",
            file=sys.stderr,
        )
        failures += 1
    else:
        print("[mapping-check] OK autoware pointcloud layout: x y z intensity return_type channel")


require_field_names(raw_lidar_topic, ("x", "y", "z", "intensity", "ring", "time"), "raw C32")
require_autoware_xyzirc_layout(lidar_topic)

for topic in (raw_lidar_topic, lidar_topic, filtered_lidar_topic, imu_raw_topic, imu_topic):
    elapsed = max(last_stamp.get(topic, 0.0) - first_stamp.get(topic, 0.0), 1e-6)
    rate = (counts[topic] - 1) / elapsed if counts[topic] > 1 else 0.0
    print(f"[mapping-check] rate {topic}: {rate:.2f} Hz")
    if counts[topic] < 2:
        print(f"[mapping-check] FAIL: insufficient samples from {topic}", file=sys.stderr)
        failures += 1

node.destroy_node()
rclpy.shutdown()

if failures:
    print(f"[mapping-check] {failures} check(s) failed", file=sys.stderr)
    sys.exit(1)

print("[mapping-check] mapping inputs look usable")
PY
