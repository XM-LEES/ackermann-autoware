from autoware_vehicle_msgs.msg import VelocityReport
from geometry_msgs.msg import TwistWithCovarianceStamped
import rclpy
from rclpy.node import Node


def velocity_report_to_twist(msg, covariance):
    twist = TwistWithCovarianceStamped()
    twist.header = msg.header
    twist.twist.twist.linear.x = float(msg.longitudinal_velocity)
    twist.twist.twist.linear.y = float(msg.lateral_velocity)
    twist.twist.twist.angular.z = float(msg.heading_rate)
    twist.twist.covariance = list(covariance)
    return twist


class VehicleVelocityConverter(Node):
    def __init__(self):
        super().__init__("vehicle_velocity_converter")
        self.declare_parameter("input_topic", "/vehicle/status/velocity_status")
        self.declare_parameter(
            "output_topic", "/sensing/vehicle_velocity_converter/twist_with_covariance"
        )
        self.declare_parameter("linear_x_covariance", 0.04)
        self.declare_parameter("linear_y_covariance", 0.04)
        self.declare_parameter("yaw_rate_covariance", 0.01)

        self._covariance = [0.0] * 36
        self._covariance[0] = float(self.get_parameter("linear_x_covariance").value)
        self._covariance[7] = float(self.get_parameter("linear_y_covariance").value)
        self._covariance[35] = float(self.get_parameter("yaw_rate_covariance").value)

        input_topic = self.get_parameter("input_topic").value
        output_topic = self.get_parameter("output_topic").value
        self._pub = self.create_publisher(TwistWithCovarianceStamped, output_topic, 10)
        self.create_subscription(VelocityReport, input_topic, self._on_velocity, 10)
        self.get_logger().info(f"Converting vehicle velocity {input_topic} -> {output_topic}")

    def _on_velocity(self, msg):
        self._pub.publish(velocity_report_to_twist(msg, self._covariance))


def main(args=None):
    rclpy.init(args=args)
    node = VehicleVelocityConverter()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
