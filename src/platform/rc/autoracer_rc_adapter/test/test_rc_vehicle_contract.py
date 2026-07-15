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

import math

import pytest

from autoracer_rc_adapter.rc_serial_interface import (
    GEAR_DRIVE,
    GEAR_LOW,
    GEAR_NEUTRAL,
    GEAR_PARK,
    GEAR_REVERSE,
    command_or_stop,
    control_to_motion,
    telemetry_to_status,
)
from autoracer_rc_adapter.rc_serial_protocol import Telemetry


def test_gear_values_match_locked_autoware_messages():
    assert GEAR_NEUTRAL == 1
    assert GEAR_DRIVE == 2
    assert GEAR_REVERSE == 20
    assert GEAR_PARK == 22
    assert GEAR_LOW == 23


def test_drive_control_uses_ackermann_yaw_rate():
    motion = control_to_motion(1.0, 0.2, GEAR_DRIVE, 0.6, 2.0, 0.3)
    assert motion == pytest.approx((1.0, 0.0, math.tan(0.2) / 0.6, False))


def test_reverse_uses_negative_velocity_and_consistent_yaw_sign():
    vx, vy, wz, stop = control_to_motion(1.0, 0.2, GEAR_REVERSE, 0.6, 2.0, 0.3)
    assert (vx, vy, stop) == pytest.approx((-1.0, 0.0, False))
    assert wz == pytest.approx(-math.tan(0.2) / 0.6)


def test_neutral_is_an_explicit_stop():
    assert control_to_motion(1.0, 0.2, GEAR_NEUTRAL, 0.6, 2.0, 0.3) == (
        0.0,
        0.0,
        0.0,
        True,
    )


def test_control_clamps_speed_and_steering():
    vx, _, wz, stop = control_to_motion(5.0, -1.0, GEAR_DRIVE, 0.6, 0.5, 0.262)
    assert vx == pytest.approx(0.5)
    assert wz == pytest.approx(0.5 * math.tan(-0.262) / 0.6)
    assert stop is False


def test_zero_speed_has_zero_yaw_rate():
    assert control_to_motion(0.0, 0.2, GEAR_DRIVE, 0.6, 0.5, 0.262) == (
        0.0,
        0.0,
        0.0,
        False,
    )


def test_telemetry_converts_yaw_rate_back_to_steering():
    telemetry = Telemetry(True, 0.4, 0.0, 0.1, 12.0)
    velocity, steering, gear = telemetry_to_status(
        telemetry, 0.1, GEAR_DRIVE, 0.6, 0.262
    )
    assert velocity == pytest.approx(0.4)
    assert steering == pytest.approx(math.atan(0.1 * 0.6 / 0.4))
    assert gear == GEAR_DRIVE


def test_zero_speed_telemetry_preserves_selected_drive_gear():
    telemetry = Telemetry(True, 0.0, 0.0, 0.0, 12.0)
    assert telemetry_to_status(telemetry, -0.1, GEAR_DRIVE, 0.6, 0.262) == (
        0.0,
        -0.1,
        GEAR_DRIVE,
    )


def test_implausible_telemetry_is_rejected():
    telemetry = Telemetry(True, math.inf, 0.0, 0.0, 12.0)
    with pytest.raises(ValueError):
        telemetry_to_status(telemetry, 0.0, GEAR_NEUTRAL, 0.6, 0.262)


def test_stale_or_disabled_command_becomes_stop():
    motion = (0.4, 0.0, 0.1, False)
    assert command_or_stop(motion, command_age=0.6, timeout=0.5, drive_enabled=True) == (
        0.0,
        0.0,
        0.0,
        True,
    )
    assert command_or_stop(motion, command_age=0.1, timeout=0.5, drive_enabled=False)[-1]
    assert command_or_stop(motion, command_age=0.1, timeout=0.5, drive_enabled=True) == motion
