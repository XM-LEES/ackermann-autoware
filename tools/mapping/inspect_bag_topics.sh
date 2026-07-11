#!/usr/bin/env bash
set -euo pipefail

BAG_PATH="${1:?usage: inspect_bag_topics.sh <bag_path>}"
ROS_DISTRO="${ROS_DISTRO:-humble}"

set +u
source "/opt/ros/${ROS_DISTRO}/setup.bash"
set -u

info="$(ros2 bag info "${BAG_PATH}")"
printf '%s\n' "${info}"

has_messages() {
  grep -Eq "Topic: $1 \\|.*Count: [1-9][0-9]*" <<< "${info}"
}

if [[ -z "${LIDAR_TOPIC:-}" ]]; then
  if has_messages /sensing/lidar/raw/pointcloud; then
    LIDAR_TOPIC=/sensing/lidar/raw/pointcloud
  elif has_messages /sensing/lidar/concatenated/pointcloud; then
    LIDAR_TOPIC=/sensing/lidar/concatenated/pointcloud
  else
    echo "ERROR: no usable C32 pointcloud topic in bag." >&2
    exit 1
  fi
fi

if [[ -z "${IMU_TOPIC:-}" ]]; then
  if has_messages /sensing/imu/imu_data; then
    IMU_TOPIC=/sensing/imu/imu_data
  elif has_messages /imu/data; then
    IMU_TOPIC=/imu/data
  else
    echo "ERROR: no usable filtered IMU topic in bag." >&2
    exit 1
  fi
fi

for topic in "${LIDAR_TOPIC}" "${IMU_TOPIC}" /tf_static; do
  if ! has_messages "${topic}"; then
    echo "ERROR: required mapping topic is missing or empty: ${topic}" >&2
    exit 1
  fi
done

if ! has_messages /tf; then
  echo "[mapping-bag] warning: /tf is absent or empty; static-TF-only bags remain usable by Super-LIO." >&2
fi

echo "[mapping-bag] selected lidar topic: ${LIDAR_TOPIC}"
echo "[mapping-bag] selected IMU topic: ${IMU_TOPIC}"

if [[ -n "${OUTPUT_ENV_FILE:-}" ]]; then
  printf 'LIDAR_TOPIC=%q\nIMU_TOPIC=%q\n' "${LIDAR_TOPIC}" "${IMU_TOPIC}" > "${OUTPUT_ENV_FILE}"
fi

export BAG_PATH LIDAR_TOPIC
python3 - <<'PY'
import math
import os
import struct
import sys
from pathlib import Path

import rosbag2_py
import yaml
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import PointCloud2, PointField

bag_path = Path(os.environ["BAG_PATH"])
topic_name = os.environ["LIDAR_TOPIC"]
metadata = yaml.safe_load((bag_path / "metadata.yaml").read_text(encoding="utf-8"))
storage_id = metadata["rosbag2_bagfile_information"].get("storage_identifier", "sqlite3")
reader = rosbag2_py.SequentialReader()
reader.open(
    rosbag2_py.StorageOptions(uri=str(bag_path), storage_id=storage_id),
    rosbag2_py.ConverterOptions("cdr", "cdr"),
)

cloud = None
while reader.has_next():
    topic, data, _ = reader.read_next()
    if topic == topic_name:
        cloud = deserialize_message(data, PointCloud2)
        break
if cloud is None:
    raise SystemExit(f"no PointCloud2 message found on {topic_name}")

expected = {
    "x": PointField.FLOAT32,
    "y": PointField.FLOAT32,
    "z": PointField.FLOAT32,
    "intensity": PointField.FLOAT32,
    "ring": PointField.UINT16,
    "time": PointField.FLOAT32,
}
fields = {field.name: field for field in cloud.fields}
for name, datatype in expected.items():
    field = fields.get(name)
    if field is None or field.datatype != datatype:
        actual = "missing" if field is None else str(field.datatype)
        print(f"ERROR: lidar field {name} has datatype {actual}, expected {datatype}", file=sys.stderr)
        raise SystemExit(1)

time_field = fields["time"]
endian = ">" if cloud.is_bigendian else "<"
values = []
for index in range(cloud.width * cloud.height):
    offset = index * cloud.point_step + time_field.offset
    value = struct.unpack_from(endian + "f", cloud.data, offset)[0]
    if math.isfinite(value):
        values.append(value)
if not values:
    raise SystemExit("ERROR: lidar time field contains no finite values")
minimum, maximum = min(values), max(values)
print(f"[mapping-bag] full lidar time range: {minimum:.6f}..{maximum:.6f} sec ({len(values)} points)")
if minimum < -1e-6 or maximum > 1.0 or maximum - minimum < 1e-4:
    raise SystemExit("ERROR: lidar point time offsets are not usable by Super-LIO")
print("[mapping-bag] C32 fields and point timing match the Super-LIO VELO32 contract")
PY
