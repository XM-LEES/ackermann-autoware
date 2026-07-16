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

"""Normalize LeiShen C32 PointCloud2 messages to Autoware PointXYZIRC."""

import numpy as np
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)
from sensor_msgs.msg import PointCloud2, PointField


_OUTPUT_FIELDS = (
    ("x", 0, PointField.FLOAT32),
    ("y", 4, PointField.FLOAT32),
    ("z", 8, PointField.FLOAT32),
    ("intensity", 12, PointField.UINT8),
    ("return_type", 13, PointField.UINT8),
    ("channel", 14, PointField.UINT16),
)

_SOURCE_TYPES = {
    PointField.UINT8: "u1",
    PointField.UINT16: "<u2",
    PointField.FLOAT32: "<f4",
}

OUTPUT_QOS = QoSProfile(
    history=HistoryPolicy.KEEP_LAST,
    depth=5,
    reliability=ReliabilityPolicy.RELIABLE,
    durability=DurabilityPolicy.VOLATILE,
)


def _source_dtype(message):
    fields = {item.name: item for item in message.fields}
    required = ("x", "y", "z", "intensity", "ring")
    missing = [name for name in required if name not in fields]
    if missing:
        raise ValueError(f"required PointCloud2 fields are missing: {', '.join(missing)}")
    for name in ("x", "y", "z"):
        if fields[name].datatype != PointField.FLOAT32 or fields[name].count != 1:
            raise ValueError(f"unsupported datatype for {name}")
    intensity_types = (PointField.UINT8, PointField.UINT16, PointField.FLOAT32)
    if fields["intensity"].datatype not in intensity_types:
        raise ValueError("unsupported datatype for intensity")
    if fields["ring"].datatype not in (PointField.UINT8, PointField.UINT16):
        raise ValueError("unsupported datatype for ring")
    if any(fields[name].count != 1 for name in required):
        raise ValueError("multi-count point fields are unsupported")
    for name in required:
        size = np.dtype(_SOURCE_TYPES[fields[name].datatype]).itemsize
        if fields[name].offset < 0 or fields[name].offset + size > message.point_step:
            raise ValueError(f"field {name} exceeds point_step")
    return np.dtype(
        {
            "names": list(required),
            "formats": [_SOURCE_TYPES[fields[name].datatype] for name in required],
            "offsets": [fields[name].offset for name in required],
            "itemsize": message.point_step,
        }
    )


def c32_to_point_xyzirc(message: PointCloud2, default_return_type: int) -> PointCloud2:
    """Return a byte-correct 16-byte PointXYZIRC cloud."""

    if message.is_bigendian:
        raise ValueError("big-endian PointCloud2 input is unsupported")
    if not 0 <= int(default_return_type) <= 255:
        raise ValueError("default_return_type must fit uint8")
    if message.height < 1 or message.width < 0 or message.point_step < 1:
        raise ValueError("PointCloud2 dimensions are invalid")
    minimum_size = message.row_step * message.height
    if len(message.data) < minimum_size:
        raise ValueError("PointCloud2 data is shorter than its dimensions")

    source = np.ndarray(
        shape=(message.height, message.width),
        dtype=_source_dtype(message),
        buffer=message.data,
        strides=(message.row_step, message.point_step),
    )
    output_dtype = np.dtype(
        [
            ("x", "<f4"),
            ("y", "<f4"),
            ("z", "<f4"),
            ("intensity", "u1"),
            ("return_type", "u1"),
            ("channel", "<u2"),
        ]
    )
    normalized = np.empty((message.height, message.width), dtype=output_dtype)
    normalized["x"] = source["x"]
    normalized["y"] = source["y"]
    normalized["z"] = source["z"]
    normalized["intensity"] = np.clip(source["intensity"], 0, 255).astype(np.uint8)
    normalized["return_type"] = int(default_return_type)
    normalized["channel"] = source["ring"].astype(np.uint16)

    output = PointCloud2()
    output.header = message.header
    output.height = message.height
    output.width = message.width
    output.fields = [
        PointField(name=name, offset=offset, datatype=datatype, count=1)
        for name, offset, datatype in _OUTPUT_FIELDS
    ]
    output.is_bigendian = False
    output.point_step = output_dtype.itemsize
    output.row_step = output.point_step * output.width
    output.data = normalized.tobytes(order="C")
    output.is_dense = message.is_dense
    return output


def main(args=None):
    """Run the C32 point layout normalization node."""

    import rclpy
    from rclpy.node import Node
    from rclpy.qos import qos_profile_sensor_data

    class C32PointCloudAdapter(Node):
        def __init__(self):
            super().__init__("c32_pointcloud_adapter")
            self.declare_parameter("default_return_type", 0)
            self._return_type = int(self.get_parameter("default_return_type").value)
            self._publisher = self.create_publisher(
                PointCloud2,
                "output",
                OUTPUT_QOS,
            )
            self.create_subscription(
                PointCloud2,
                "input",
                self._on_cloud,
                qos_profile_sensor_data,
            )

        def _on_cloud(self, message):
            try:
                normalized = c32_to_point_xyzirc(message, self._return_type)
            except ValueError as error:
                self.get_logger().warning(str(error), throttle_duration_sec=5.0)
                return
            self._publisher.publish(normalized)

    rclpy.init(args=args)
    node = C32PointCloudAdapter()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
