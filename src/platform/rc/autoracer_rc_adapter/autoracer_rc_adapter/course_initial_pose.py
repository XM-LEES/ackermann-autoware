"""Derive the RC localization seed from the validated fixed-course start."""

import csv
import math
from pathlib import Path
from typing import Tuple


PoseTuple = Tuple[float, float, float, float, float, float, float]


def load_course_initial_pose(course_path: Path) -> PoseTuple:
    """Return ``x, y, z, qx, qy, qz, qw`` from the first course sample."""

    csv_path = Path(course_path) / "course.csv"
    try:
        with csv_path.open(newline="", encoding="utf-8") as stream:
            row = next(csv.DictReader(stream))
        x, y, z, yaw = (
            float(row[name]) for name in ("x", "y", "z", "yaw")
        )
    except (
        FileNotFoundError,
        KeyError,
        StopIteration,
        TypeError,
        ValueError,
    ) as error:
        raise ValueError(
            f"invalid RC course start in {csv_path}: {error}"
        ) from error
    if not all(math.isfinite(value) for value in (x, y, z, yaw)):
        raise ValueError(
            f"RC course start must contain finite values: {csv_path}"
        )
    return (x, y, z, 0.0, 0.0, math.sin(yaw / 2.0), math.cos(yaw / 2.0))
