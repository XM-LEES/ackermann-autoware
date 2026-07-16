import math

import pytest

from autoracer_rc_adapter.course_initial_pose import load_course_initial_pose


def test_course_start_becomes_a_map_pose_guess(tmp_path):
    course = tmp_path / "course"
    course.mkdir()
    (course / "course.csv").write_text(
        "s,x,y,z,yaw,curvature,left_offset,right_offset,target_velocity,target_acceleration\n"
        "0.0,1.25,-0.5,0.1,0.4,0.0,0.4,0.4,0.1,0.0\n",
        encoding="utf-8",
    )

    pose = load_course_initial_pose(course)

    assert pose == pytest.approx(
        (1.25, -0.5, 0.1, 0.0, 0.0, math.sin(0.2), math.cos(0.2))
    )


def test_course_start_rejects_non_finite_values(tmp_path):
    course = tmp_path / "course"
    course.mkdir()
    (course / "course.csv").write_text(
        "s,x,y,z,yaw,curvature,left_offset,right_offset,target_velocity,target_acceleration\n"
        "0.0,nan,0.0,0.0,0.0,0.0,0.4,0.4,0.1,0.0\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="finite"):
        load_course_initial_pose(course)
