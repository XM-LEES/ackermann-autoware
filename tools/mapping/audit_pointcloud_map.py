#!/usr/bin/env python3
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np


def parse_args():
    parser = argparse.ArgumentParser(
        description="Audit a flat-road Super-LIO PCD before Autoware packaging."
    )
    parser.add_argument("pcd", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-ground-tilt-deg", type=float, default=3.0)
    parser.add_argument("--min-ground-fraction", type=float, default=0.15)
    parser.add_argument("--ransac-distance", type=float, default=0.12)
    parser.add_argument("--sample-size", type=int, default=180000)
    parser.add_argument("--iterations", type=int, default=500)
    return parser.parse_args()


def read_pcd_header(path):
    values = {}
    with path.open("rb") as stream:
        while True:
            line = stream.readline()
            if not line:
                raise ValueError("PCD header does not contain a DATA line")
            decoded = line.decode("ascii").strip()
            if not decoded or decoded.startswith("#"):
                continue
            key, *items = decoded.split()
            values[key] = items
            if key == "DATA":
                data_offset = stream.tell()
                break

    required = ("FIELDS", "SIZE", "TYPE", "COUNT", "POINTS", "DATA")
    missing = [key for key in required if key not in values]
    if missing:
        raise ValueError(f"PCD header is missing: {', '.join(missing)}")
    if values["DATA"] != ["binary"]:
        raise ValueError("only binary PCD files are supported")
    if values["FIELDS"] != ["x", "y", "z", "intensity"]:
        raise ValueError("expected Super-LIO fields: x y z intensity")
    if values["SIZE"] != ["4", "4", "4", "4"]:
        raise ValueError("expected four 32-bit fields")
    if values["TYPE"] != ["F", "F", "F", "F"]:
        raise ValueError("expected four floating-point fields")
    if values["COUNT"] != ["1", "1", "1", "1"]:
        raise ValueError("expected scalar PCD fields")

    point_count = int(values["POINTS"][0])
    expected_size = data_offset + point_count * 16
    actual_size = path.stat().st_size
    if actual_size < expected_size:
        raise ValueError(
            f"PCD payload is truncated: expected {expected_size}, got {actual_size} bytes"
        )
    return data_offset, point_count


def summarize_points(cloud):
    finite_count = 0
    zero_count = 0
    bounds_min = np.full(3, np.inf, dtype=np.float64)
    bounds_max = np.full(3, -np.inf, dtype=np.float64)
    chunk_size = 1_000_000

    for start in range(0, len(cloud), chunk_size):
        xyz = np.asarray(cloud[start : start + chunk_size, :3])
        finite = np.isfinite(xyz).all(axis=1)
        finite_count += int(finite.sum())
        zero_count += int(np.count_nonzero((xyz == 0.0).all(axis=1)))
        if finite.any():
            finite_xyz = xyz[finite]
            bounds_min = np.minimum(bounds_min, finite_xyz.min(axis=0))
            bounds_max = np.maximum(bounds_max, finite_xyz.max(axis=0))

    return finite_count, zero_count, bounds_min, bounds_max


def fit_ground_plane(cloud, sample_size, iterations, distance_threshold):
    rng = np.random.default_rng(20260710)
    sample_size = min(sample_size, len(cloud))
    indices = rng.choice(len(cloud), size=sample_size, replace=False)
    points = np.asarray(cloud[indices, :3], dtype=np.float64)
    points = points[np.isfinite(points).all(axis=1)]
    if len(points) < 3:
        raise ValueError("not enough finite points for a ground-plane fit")

    best_mask = None
    best_count = 0
    for _ in range(iterations):
        first, second, third = points[rng.choice(len(points), size=3, replace=False)]
        normal = np.cross(second - first, third - first)
        magnitude = np.linalg.norm(normal)
        if magnitude < 0.5:
            continue
        normal /= magnitude
        if abs(normal[2]) < math.cos(math.radians(45.0)):
            continue
        offset = -normal.dot(first)
        mask = np.abs(points @ normal + offset) < distance_threshold
        count = int(mask.sum())
        if count > best_count:
            best_count = count
            best_mask = mask

    if best_mask is None:
        raise ValueError("no horizontal ground-plane candidate was found")

    inliers = points[best_mask]
    center = inliers.mean(axis=0)
    _, _, right_vectors = np.linalg.svd(inliers - center, full_matrices=False)
    normal = right_vectors[-1]
    if normal[2] < 0:
        normal = -normal
    residual = np.abs((inliers - center) @ normal)
    tilt = math.degrees(math.acos(float(np.clip(normal[2], -1.0, 1.0))))
    return {
        "normal": [float(value) for value in normal],
        "tilt_degrees": tilt,
        "sample_points": int(len(points)),
        "inlier_points": int(len(inliers)),
        "inlier_fraction": float(len(inliers) / len(points)),
        "residual_median_m": float(np.median(residual)),
        "residual_p95_m": float(np.percentile(residual, 95)),
        "ransac_distance_m": distance_threshold,
    }


def audit(args):
    if not args.pcd.is_file():
        raise ValueError(f"PCD does not exist: {args.pcd}")
    data_offset, point_count = read_pcd_header(args.pcd)
    cloud = np.memmap(
        args.pcd,
        mode="r",
        dtype="<f4",
        offset=data_offset,
        shape=(point_count, 4),
    )
    finite_count, zero_count, bounds_min, bounds_max = summarize_points(cloud)
    plane = fit_ground_plane(
        cloud,
        sample_size=args.sample_size,
        iterations=args.iterations,
        distance_threshold=args.ransac_distance,
    )

    failures = []
    if finite_count != point_count:
        failures.append(f"{point_count - finite_count} points contain non-finite XYZ")
    if zero_count:
        failures.append(f"{zero_count} points have all-zero XYZ")
    if plane["tilt_degrees"] > args.max_ground_tilt_deg:
        failures.append(
            f"ground tilt {plane['tilt_degrees']:.3f} deg exceeds "
            f"{args.max_ground_tilt_deg:.3f} deg"
        )
    if plane["inlier_fraction"] < args.min_ground_fraction:
        failures.append(
            f"ground fraction {plane['inlier_fraction']:.3f} is below "
            f"{args.min_ground_fraction:.3f}"
        )

    return {
        "schema_version": 1,
        "source_pcd": str(args.pcd.resolve()),
        "passed": not failures,
        "failures": failures,
        "point_count": point_count,
        "finite_xyz_count": finite_count,
        "all_zero_xyz_count": zero_count,
        "bounds_m": {
            "min": [float(value) for value in bounds_min],
            "max": [float(value) for value in bounds_max],
            "span": [float(value) for value in bounds_max - bounds_min],
        },
        "ground_plane": plane,
        "limits": {
            "max_ground_tilt_degrees": args.max_ground_tilt_deg,
            "min_ground_fraction": args.min_ground_fraction,
        },
    }


def main():
    args = parse_args()
    try:
        report = audit(args)
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
