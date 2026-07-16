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

import struct

import pytest
from rclpy.qos import ReliabilityPolicy
from sensor_msgs.msg import PointCloud2, PointField
from std_msgs.msg import Header

from autoracer_rc_adapter.c32_pointcloud_adapter import (
    OUTPUT_QOS,
    c32_to_point_xyzirc,
)


def field(name, offset, datatype):
    return PointField(name=name, offset=offset, datatype=datatype, count=1)


def make_cloud(points, *, height=1, fields=None, point_step=18):
    if fields is None:
        fields = [
            field("x", 0, PointField.FLOAT32),
            field("y", 4, PointField.FLOAT32),
            field("z", 8, PointField.FLOAT32),
            field("intensity", 12, PointField.FLOAT32),
            field("ring", 16, PointField.UINT16),
        ]
    data = b"".join(struct.pack("<ffffH", *point) for point in points)
    return PointCloud2(
        header=Header(frame_id="lidar_top"),
        height=height,
        width=len(points) // height,
        fields=fields,
        is_bigendian=False,
        point_step=point_step,
        row_step=point_step * (len(points) // height),
        data=data,
        is_dense=True,
    )


def test_output_has_exact_xyzirc_layout():
    output = c32_to_point_xyzirc(make_cloud([(1.0, 2.0, 3.0, 42.0, 7)]), 1)
    assert [(item.name, item.offset, item.datatype) for item in output.fields] == [
        ("x", 0, PointField.FLOAT32),
        ("y", 4, PointField.FLOAT32),
        ("z", 8, PointField.FLOAT32),
        ("intensity", 12, PointField.UINT8),
        ("return_type", 13, PointField.UINT8),
        ("channel", 14, PointField.UINT16),
    ]
    assert output.point_step == 16
    assert output.row_step == 16
    assert struct.unpack("<fffBBH", bytes(output.data)) == pytest.approx(
        (1.0, 2.0, 3.0, 42, 1, 7)
    )


def test_output_qos_satisfies_reliable_autoware_preprocessor_subscribers():
    assert OUTPUT_QOS.reliability == ReliabilityPolicy.RELIABLE


def test_preserves_header_stamp_and_organized_shape():
    source = make_cloud(
        [(1.0, 2.0, 3.0, 1.0, 0), (4.0, 5.0, 6.0, 2.0, 1)],
        height=2,
    )
    source.header.stamp.sec = 12
    source.header.stamp.nanosec = 34
    output = c32_to_point_xyzirc(source, 0)
    assert output.header == source.header
    assert (output.height, output.width) == (2, 1)
    assert output.row_step == 16


def test_clamps_intensity_and_converts_ring_to_channel():
    source = make_cloud(
        [(0.0, 0.0, 0.0, -2.0, 31), (0.0, 0.0, 0.0, 999.0, 65535)]
    )
    output = c32_to_point_xyzirc(source, 2)
    first = struct.unpack_from("<fffBBH", output.data, 0)
    second = struct.unpack_from("<fffBBH", output.data, 16)
    assert first[3:] == (0, 2, 31)
    assert second[3:] == (255, 2, 65535)


def test_missing_xyz_is_rejected():
    source = make_cloud(
        [(1.0, 2.0, 3.0, 4.0, 5)],
        fields=[field("x", 0, PointField.FLOAT32)],
    )
    with pytest.raises(ValueError, match="required"):
        c32_to_point_xyzirc(source, 0)


def test_unsupported_source_datatype_is_rejected():
    source = make_cloud([(1.0, 2.0, 3.0, 4.0, 5)])
    source.fields[0].datatype = PointField.FLOAT64
    with pytest.raises(ValueError, match="datatype"):
        c32_to_point_xyzirc(source, 0)


def test_big_endian_source_is_rejected():
    source = make_cloud([(1.0, 2.0, 3.0, 4.0, 5)])
    source.is_bigendian = True
    with pytest.raises(ValueError, match="big-endian"):
        c32_to_point_xyzirc(source, 0)
