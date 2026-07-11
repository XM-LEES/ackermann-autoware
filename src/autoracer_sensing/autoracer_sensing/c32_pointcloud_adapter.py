import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import (
    QoSDurabilityPolicy,
    QoSHistoryPolicy,
    QoSProfile,
    QoSReliabilityPolicy,
    qos_profile_sensor_data,
)
from sensor_msgs.msg import PointCloud2, PointField


_POINT_FIELD_DTYPES = {
    PointField.INT8: np.int8,
    PointField.UINT8: np.uint8,
    PointField.INT16: np.int16,
    PointField.UINT16: np.uint16,
    PointField.INT32: np.int32,
    PointField.UINT32: np.uint32,
    PointField.FLOAT32: np.float32,
    PointField.FLOAT64: np.float64,
}

_XYZIRC_DTYPE = np.dtype(
    {
        "names": ["x", "y", "z", "intensity", "return_type", "channel"],
        "formats": [np.float32, np.float32, np.float32, np.uint8, np.uint8, np.uint16],
        "offsets": [0, 4, 8, 12, 13, 14],
        "itemsize": 16,
    }
)


def _numpy_dtype_from_fields(fields, point_step):
    names = []
    formats = []
    offsets = []
    for field in fields:
        base_dtype = _POINT_FIELD_DTYPES.get(field.datatype)
        if base_dtype is None or field.count != 1:
            continue
        names.append(field.name)
        formats.append(base_dtype)
        offsets.append(field.offset)
    return np.dtype(
        {"names": names, "formats": formats, "offsets": offsets, "itemsize": point_step}
    )


def _require_fields(dtype, required):
    missing = sorted(set(required).difference(dtype.names or ()))
    if missing:
        raise ValueError("PointCloud2 missing fields: " + ", ".join(missing))


def reliable_sensor_qos(depth=10):
    return QoSProfile(
        history=QoSHistoryPolicy.KEEP_LAST,
        depth=int(depth),
        reliability=QoSReliabilityPolicy.RELIABLE,
        durability=QoSDurabilityPolicy.VOLATILE,
    )


def c32_to_point_xyzirc(msg, default_return_type=1):
    dtype = _numpy_dtype_from_fields(msg.fields, msg.point_step)
    _require_fields(dtype, {"x", "y", "z"})

    count = int(msg.width * msg.height)
    source = np.frombuffer(msg.data, dtype=dtype, count=count)
    output = np.zeros(count, dtype=_XYZIRC_DTYPE)
    output["x"] = source["x"].astype(np.float32, copy=False)
    output["y"] = source["y"].astype(np.float32, copy=False)
    output["z"] = source["z"].astype(np.float32, copy=False)

    if "intensity" in dtype.names:
        intensity = source["intensity"].astype(np.float32, copy=False)
        output["intensity"] = np.clip(np.rint(intensity), 0, 255).astype(np.uint8)

    channel_field = "ring" if "ring" in (dtype.names or ()) else "channel"
    if channel_field in (dtype.names or ()):
        output["channel"] = np.clip(source[channel_field], 0, np.iinfo(np.uint16).max).astype(
            np.uint16
        )

    output["return_type"] = np.uint8(default_return_type)

    converted = PointCloud2()
    converted.header = msg.header
    converted.height = msg.height
    converted.width = msg.width
    converted.fields = [
        PointField(name="x", offset=0, datatype=PointField.FLOAT32, count=1),
        PointField(name="y", offset=4, datatype=PointField.FLOAT32, count=1),
        PointField(name="z", offset=8, datatype=PointField.FLOAT32, count=1),
        PointField(name="intensity", offset=12, datatype=PointField.UINT8, count=1),
        PointField(name="return_type", offset=13, datatype=PointField.UINT8, count=1),
        PointField(name="channel", offset=14, datatype=PointField.UINT16, count=1),
    ]
    converted.is_bigendian = False
    converted.point_step = _XYZIRC_DTYPE.itemsize
    converted.row_step = converted.point_step * converted.width
    converted.is_dense = msg.is_dense
    converted.data = output.tobytes()
    return converted


class C32PointCloudAdapter(Node):
    def __init__(self):
        super().__init__("c32_pointcloud_adapter")
        self.declare_parameter("input_topic", "/sensing/lidar/raw/pointcloud")
        self.declare_parameter("output_topic", "/sensing/lidar/concatenated/pointcloud")
        self.declare_parameter("default_return_type", 1)

        self._default_return_type = int(self.get_parameter("default_return_type").value)
        input_topic = self.get_parameter("input_topic").value
        output_topic = self.get_parameter("output_topic").value
        self._publisher = self.create_publisher(PointCloud2, output_topic, reliable_sensor_qos())
        self.create_subscription(PointCloud2, input_topic, self._on_cloud, qos_profile_sensor_data)
        self.get_logger().info(f"Adapting C32 pointcloud {input_topic} -> {output_topic}")

    def _on_cloud(self, msg):
        try:
            converted = c32_to_point_xyzirc(msg, self._default_return_type)
        except Exception as exc:  # noqa: BLE001
            self.get_logger().warn(
                f"Failed to adapt C32 pointcloud: {exc}", throttle_duration_sec=2.0
            )
            return
        self._publisher.publish(converted)


def main(args=None):
    rclpy.init(args=args)
    node = C32PointCloudAdapter()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
