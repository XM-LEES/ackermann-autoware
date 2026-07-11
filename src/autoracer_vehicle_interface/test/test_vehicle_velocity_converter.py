import pytest

from autoware_vehicle_msgs.msg import VelocityReport

from autoracer_vehicle_interface.vehicle_velocity_converter import velocity_report_to_twist


def test_velocity_report_to_twist_uses_autoware_stop_check_topic_layout():
    velocity = VelocityReport()
    velocity.header.frame_id = "base_link"
    velocity.longitudinal_velocity = 1.2
    velocity.lateral_velocity = -0.1
    velocity.heading_rate = 0.3
    covariance = [0.0] * 36
    covariance[0] = 0.04
    covariance[7] = 0.05
    covariance[35] = 0.01

    twist = velocity_report_to_twist(velocity, covariance)

    assert twist.header.frame_id == "base_link"
    assert twist.twist.twist.linear.x == pytest.approx(1.2)
    assert twist.twist.twist.linear.y == pytest.approx(-0.1)
    assert twist.twist.twist.angular.z == pytest.approx(0.3)
    assert twist.twist.covariance[0] == pytest.approx(0.04)
    assert twist.twist.covariance[7] == pytest.approx(0.05)
    assert twist.twist.covariance[35] == pytest.approx(0.01)
