import math
from pathlib import Path

from autoware_planning_msgs.msg import Trajectory, TrajectoryPoint
from builtin_interfaces.msg import Duration
from geometry_msgs.msg import Point, Quaternion
import rclpy
from rclpy._rclpy_pybind11 import RCLError
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from visualization_msgs.msg import Marker, MarkerArray

from autoracer_planning.course_asset import load_runtime_course_asset


def _duration_from_seconds(seconds: float) -> Duration:
    duration = Duration()
    duration.sec = int(seconds)
    duration.nanosec = int(round((seconds - duration.sec) * 1_000_000_000))
    if duration.nanosec >= 1_000_000_000:
        duration.sec += 1
        duration.nanosec -= 1_000_000_000
    return duration


def _yaw_to_quaternion(yaw: float) -> Quaternion:
    quaternion = Quaternion()
    quaternion.z = math.sin(0.5 * yaw)
    quaternion.w = math.cos(0.5 * yaw)
    return quaternion


def course_to_trajectory(manifest: dict, samples) -> Trajectory:
    trajectory = Trajectory()
    trajectory.header.frame_id = manifest["frame_id"]
    elapsed = 0.0
    for index, sample in enumerate(samples):
        if index > 0:
            previous = samples[index - 1]
            ds = sample.s - previous.s
            average_speed = 0.5 * (
                previous.target_velocity + sample.target_velocity
            )
            elapsed += ds / max(average_speed, 0.1)
        point = TrajectoryPoint()
        point.time_from_start = _duration_from_seconds(elapsed)
        point.pose.position.x = sample.x
        point.pose.position.y = sample.y
        point.pose.position.z = sample.z
        point.pose.orientation = _yaw_to_quaternion(sample.yaw)
        point.longitudinal_velocity_mps = sample.target_velocity
        point.acceleration_mps2 = sample.target_acceleration
        trajectory.points.append(point)
    return trajectory


def course_to_markers(manifest: dict, samples) -> MarkerArray:
    frame_id = manifest["frame_id"]
    line = Marker()
    line.header.frame_id = frame_id
    line.ns = "autoracer_fixed_course"
    line.id = 0
    line.type = Marker.LINE_STRIP
    line.action = Marker.ADD
    line.pose.orientation.w = 1.0
    line.scale.x = 0.5
    line.color.r = 1.0
    line.color.g = 0.12
    line.color.b = 0.04
    line.color.a = 1.0
    for sample in samples:
        line.points.append(
            Point(x=float(sample.x), y=float(sample.y), z=float(sample.z + 0.15))
        )

    endpoints = []
    for marker_id, namespace, sample, color in (
        (1, "autoracer_fixed_course_start", samples[0], (0.0, 1.0, 0.0)),
        (2, "autoracer_fixed_course_finish", samples[-1], (0.0, 0.25, 1.0)),
    ):
        marker = Marker()
        marker.header.frame_id = frame_id
        marker.ns = namespace
        marker.id = marker_id
        marker.type = Marker.SPHERE
        marker.action = Marker.ADD
        marker.pose.position.x = float(sample.x)
        marker.pose.position.y = float(sample.y)
        marker.pose.position.z = float(sample.z + 0.3)
        marker.pose.orientation.w = 1.0
        marker.scale.x = marker.scale.y = marker.scale.z = 1.2
        marker.color.r, marker.color.g, marker.color.b = color
        marker.color.a = 1.0
        endpoints.append(marker)
    return MarkerArray(markers=[line, *endpoints])


def course_asset_label(manifest: dict) -> str:
    return str(manifest.get("version") or manifest["map_id"])


class FixedCoursePublisher(Node):
    def __init__(self):
        super().__init__("fixed_course_publisher")
        self.declare_parameter("course_path", "")
        self.declare_parameter("map_path", "")
        self.declare_parameter("trajectory_topic", "/planning/global_trajectory")
        self.declare_parameter("visualization_topic", "")
        self.declare_parameter("publish_visualization", False)

        course_path_value = str(self.get_parameter("course_path").value)
        if not course_path_value:
            raise RuntimeError("course_path parameter is required")
        course_path = Path(course_path_value)
        map_path_value = str(self.get_parameter("map_path").value)
        if not map_path_value:
            raise RuntimeError("map_path parameter is required")
        manifest, samples = load_runtime_course_asset(course_path, Path(map_path_value))
        if manifest.get("frame_id") != "map":
            raise RuntimeError(f"fixed course frame must be map: {manifest.get('frame_id')!r}")

        qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self._publisher = self.create_publisher(
            Trajectory, str(self.get_parameter("trajectory_topic").value), qos
        )
        self._trajectory = course_to_trajectory(manifest, samples)
        self._trajectory.header.stamp = self.get_clock().now().to_msg()
        self._publisher.publish(self._trajectory)
        visualization_topic = str(self.get_parameter("visualization_topic").value)
        self._marker_publisher = None
        self._marker_timer = None
        if bool(self.get_parameter("publish_visualization").value) and visualization_topic:
            self._marker_publisher = self.create_publisher(
                MarkerArray, visualization_topic, qos
            )
            self._markers = course_to_markers(manifest, samples)
            for marker in self._markers.markers:
                marker.header.stamp = self._trajectory.header.stamp
            self._marker_publisher.publish(self._markers)
            self._marker_timer = self.create_timer(
                1.0, lambda: self._marker_publisher.publish(self._markers)
            )
        self.get_logger().info(
            "Published validated fixed course: "
            f"asset={course_asset_label(manifest)} points={len(samples)} "
            f"length_m={samples[-1].s:.3f} sha256="
            f"{manifest['assets']['course.csv']['sha256']}"
        )


def _shutdown_if_context_ok():
    if not rclpy.ok():
        return
    try:
        rclpy.shutdown()
    except RCLError as exc:
        if "rcl_shutdown already called" not in str(exc):
            raise


def main():
    rclpy.init()
    node = FixedCoursePublisher()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        _shutdown_if_context_ok()


if __name__ == "__main__":
    main()
