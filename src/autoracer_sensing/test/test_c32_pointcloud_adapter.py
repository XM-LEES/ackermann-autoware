import numpy as np
import rclpy
from rclpy.qos import QoSReliabilityPolicy
from sensor_msgs.msg import PointCloud2, PointField

from autoracer_sensing.c32_pointcloud_adapter import c32_to_point_xyzirc, reliable_sensor_qos


def make_c32_cloud():
    points = np.zeros(
        2,
        dtype={
            "names": ["x", "y", "z", "padding", "intensity", "ring", "time"],
            "formats": [
                np.float32,
                np.float32,
                np.float32,
                np.float32,
                np.float32,
                np.uint16,
                np.float32,
            ],
            "offsets": [0, 4, 8, 12, 16, 20, 24],
            "itemsize": 32,
        },
    )
    points["x"] = [1.0, 2.0]
    points["y"] = [3.0, 4.0]
    points["z"] = [5.0, 6.0]
    points["intensity"] = [12.4, 300.0]
    points["ring"] = [7, 31]
    points["time"] = [0.001, 0.002]

    msg = PointCloud2()
    msg.header.stamp = rclpy.time.Time(seconds=42.0).to_msg()
    msg.header.frame_id = "lidar_top"
    msg.height = 1
    msg.width = len(points)
    msg.fields = [
        PointField(name="x", offset=0, datatype=PointField.FLOAT32, count=1),
        PointField(name="y", offset=4, datatype=PointField.FLOAT32, count=1),
        PointField(name="z", offset=8, datatype=PointField.FLOAT32, count=1),
        PointField(name="intensity", offset=16, datatype=PointField.FLOAT32, count=1),
        PointField(name="ring", offset=20, datatype=PointField.UINT16, count=1),
        PointField(name="time", offset=24, datatype=PointField.FLOAT32, count=1),
    ]
    msg.is_bigendian = False
    msg.point_step = 32
    msg.row_step = msg.point_step * msg.width
    msg.is_dense = True
    msg.data = points.tobytes()
    return msg


def test_c32_adapter_outputs_autoware_point_xyzirc_layout():
    converted = c32_to_point_xyzirc(make_c32_cloud(), default_return_type=1)

    assert converted.header.frame_id == "lidar_top"
    assert converted.width == 2
    assert converted.height == 1
    assert converted.point_step == 16
    assert converted.row_step == 32
    assert [(f.name, f.offset, f.datatype, f.count) for f in converted.fields] == [
        ("x", 0, PointField.FLOAT32, 1),
        ("y", 4, PointField.FLOAT32, 1),
        ("z", 8, PointField.FLOAT32, 1),
        ("intensity", 12, PointField.UINT8, 1),
        ("return_type", 13, PointField.UINT8, 1),
        ("channel", 14, PointField.UINT16, 1),
    ]

    dtype = np.dtype(
        {
            "names": ["x", "y", "z", "intensity", "return_type", "channel"],
            "formats": [np.float32, np.float32, np.float32, np.uint8, np.uint8, np.uint16],
            "offsets": [0, 4, 8, 12, 13, 14],
            "itemsize": 16,
        }
    )
    points = np.frombuffer(converted.data, dtype=dtype, count=2)

    np.testing.assert_allclose(points["x"], [1.0, 2.0])
    np.testing.assert_allclose(points["y"], [3.0, 4.0])
    np.testing.assert_allclose(points["z"], [5.0, 6.0])
    np.testing.assert_array_equal(points["intensity"], [12, 255])
    np.testing.assert_array_equal(points["return_type"], [1, 1])
    np.testing.assert_array_equal(points["channel"], [7, 31])


def test_c32_adapter_output_qos_matches_autoware_reliable_subscribers():
    assert reliable_sensor_qos().reliability == QoSReliabilityPolicy.RELIABLE
