import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
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


def pointcloud2_to_xyzi(msg, min_range_m=0.0, max_range_m=0.0):
    dtype = _numpy_dtype_from_fields(msg.fields, msg.point_step)
    if not {"x", "y", "z"}.issubset(dtype.names or ()):
        raise ValueError("PointCloud2 must contain x, y, and z fields")

    count = int(msg.width * msg.height)
    cloud = np.frombuffer(msg.data, dtype=dtype, count=count)
    intensity = cloud["intensity"] if "intensity" in dtype.names else np.zeros(count)
    points = np.column_stack(
        (
            cloud["x"].astype(np.float32, copy=False),
            cloud["y"].astype(np.float32, copy=False),
            cloud["z"].astype(np.float32, copy=False),
            intensity.astype(np.float32, copy=False),
        )
    )

    finite = np.isfinite(points[:, :3]).all(axis=1)
    points = points[finite]

    if min_range_m > 0.0 or max_range_m > 0.0:
        distances = np.linalg.norm(points[:, :3], axis=1)
        mask = np.ones(len(points), dtype=bool)
        if min_range_m > 0.0:
            mask &= distances >= float(min_range_m)
        if max_range_m > 0.0:
            mask &= distances <= float(max_range_m)
        points = points[mask]

    return points.astype(np.float32, copy=False)


def voxel_downsample_xyzi(points, leaf_size_m, max_points=0):
    if len(points) == 0:
        return points

    if leaf_size_m > 0.0:
        keys = np.floor(points[:, :3] / float(leaf_size_m)).astype(np.int64)
        _, indices = np.unique(keys, axis=0, return_index=True)
        points = points[np.sort(indices)]

    if max_points > 0 and len(points) > max_points:
        stride = int(np.ceil(len(points) / float(max_points)))
        points = points[::stride][:max_points]

    return points.astype(np.float32, copy=False)


def xyzi_to_pointcloud2(points, header):
    msg = PointCloud2()
    msg.header = header
    msg.height = 1
    msg.width = int(len(points))
    msg.fields = [
        PointField(name="x", offset=0, datatype=PointField.FLOAT32, count=1),
        PointField(name="y", offset=4, datatype=PointField.FLOAT32, count=1),
        PointField(name="z", offset=8, datatype=PointField.FLOAT32, count=1),
        PointField(name="intensity", offset=12, datatype=PointField.FLOAT32, count=1),
    ]
    msg.is_bigendian = False
    msg.point_step = 16
    msg.row_step = msg.point_step * msg.width
    msg.is_dense = True
    msg.data = np.asarray(points, dtype=np.float32).tobytes()
    return msg


class PointCloudVoxelFilter(Node):
    def __init__(self):
        super().__init__("pointcloud_voxel_filter")
        self.declare_parameter("input_topic", "/sensing/lidar/concatenated/pointcloud")
        self.declare_parameter("output_topic", "/sensing/lidar/filtered/pointcloud")
        self.declare_parameter("leaf_size_m", 0.2)
        self.declare_parameter("min_range_m", 0.15)
        self.declare_parameter("max_range_m", 60.0)
        self.declare_parameter("max_points", 3000)

        self._leaf_size_m = float(self.get_parameter("leaf_size_m").value)
        self._min_range_m = float(self.get_parameter("min_range_m").value)
        self._max_range_m = float(self.get_parameter("max_range_m").value)
        self._max_points = int(self.get_parameter("max_points").value)
        self._frames = 0

        self._pub = self.create_publisher(
            PointCloud2, self.get_parameter("output_topic").value, qos_profile_sensor_data
        )
        self.create_subscription(
            PointCloud2,
            self.get_parameter("input_topic").value,
            self._on_cloud,
            qos_profile_sensor_data,
        )
        self.get_logger().info(
            "Filtering pointcloud %s -> %s leaf=%.3f max_points=%d"
            % (
                self.get_parameter("input_topic").value,
                self.get_parameter("output_topic").value,
                self._leaf_size_m,
                self._max_points,
            )
        )

    def _on_cloud(self, msg):
        try:
            points = pointcloud2_to_xyzi(msg, self._min_range_m, self._max_range_m)
            points = voxel_downsample_xyzi(points, self._leaf_size_m, self._max_points)
        except Exception as exc:  # noqa: BLE001
            self.get_logger().warn(f"Failed to filter pointcloud: {exc}", throttle_duration_sec=2.0)
            return

        self._pub.publish(xyzi_to_pointcloud2(points, msg.header))
        self._frames += 1
        if self._frames == 1:
            self.get_logger().info(f"Published filtered pointcloud with {len(points)} points")


def main(args=None):
    rclpy.init(args=args)
    node = PointCloudVoxelFilter()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
