#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

import numpy as np
import yaml


def read_header(path: Path):
    header = {}
    with path.open("rb") as stream:
        while True:
            line = stream.readline()
            if not line:
                raise ValueError(f"PCD header ended before DATA: {path}")
            text = line.decode("ascii").strip()
            if not text or text.startswith("#"):
                continue
            key, *values = text.split()
            header[key.upper()] = values
            if key.upper() == "DATA":
                return header, stream.tell()


def field_layout(header):
    fields = header.get("FIELDS", [])
    sizes = [int(value) for value in header.get("SIZE", [])]
    types = header.get("TYPE", [])
    counts = [int(value) for value in header.get("COUNT", ["1"] * len(fields))]
    if not fields or not (len(fields) == len(sizes) == len(types) == len(counts)):
        raise ValueError("unsupported PCD field layout")

    offsets = {}
    point_step = 0
    for name, size, type_name, count in zip(fields, sizes, types, counts):
        offsets[name] = (point_step, size, type_name, count)
        point_step += size * count
    return fields, offsets, point_step


def scalar_dtype(size: int, type_name: str):
    dtypes = {
        (4, "F"): "<f4",
        (8, "F"): "<f8",
        (4, "I"): "<i4",
        (4, "U"): "<u4",
    }
    try:
        return np.dtype(dtypes[(size, type_name)])
    except KeyError as error:
        raise ValueError(f"unsupported PCD scalar: TYPE={type_name} SIZE={size}") from error


def xy_bounds(path: Path):
    header, data_offset = read_header(path)
    fields, offsets, point_step = field_layout(header)
    if "x" not in offsets or "y" not in offsets:
        raise ValueError(f"PCD lacks x/y fields: {path}")

    data_type = header.get("DATA", [""])[0].lower()
    point_count = int((header.get("POINTS") or header.get("WIDTH") or ["0"])[0])
    if data_type == "ascii":
        values = np.loadtxt(path, skiprows=sum(1 for _ in path.open("rb")) - point_count)
        values = np.atleast_2d(values)
        x_values = values[:, fields.index("x")]
        y_values = values[:, fields.index("y")]
    elif data_type == "binary":
        payload = np.memmap(
            path, mode="r", dtype=np.uint8, offset=data_offset, shape=(point_count, point_step)
        )
        x_offset, x_size, x_type, x_count = offsets["x"]
        y_offset, y_size, y_type, y_count = offsets["y"]
        if x_count != 1 or y_count != 1:
            raise ValueError("x/y fields must be scalar")
        x_values = np.ndarray(
            (point_count,), scalar_dtype(x_size, x_type), payload, offset=x_offset, strides=(point_step,)
        )
        y_values = np.ndarray(
            (point_count,), scalar_dtype(y_size, y_type), payload, offset=y_offset, strides=(point_step,)
        )
    else:
        raise ValueError(f"unsupported PCD DATA mode: {data_type}")

    finite = np.isfinite(x_values) & np.isfinite(y_values)
    if not finite.any():
        raise ValueError(f"PCD has no finite XY points: {path}")
    return (
        float(x_values[finite].min()),
        float(y_values[finite].min()),
        float(x_values[finite].max()),
        float(y_values[finite].max()),
    )


def validate(map_dir: Path):
    metadata_path = map_dir / "pointcloud_map_metadata.yaml"
    pointcloud_path = map_dir / "pointcloud_map.pcd"
    metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
    x_resolution = float(metadata["x_resolution"])
    y_resolution = float(metadata["y_resolution"])
    pcd_files = [pointcloud_path] if pointcloud_path.is_file() else sorted(pointcloud_path.glob("*.pcd"))
    if not pcd_files:
        raise ValueError(f"no PCD files found in {pointcloud_path}")

    tolerance = 1e-4
    for pcd in pcd_files:
        if pcd.name not in metadata:
            raise ValueError(f"metadata entry missing for {pcd.name}")
        origin_x, origin_y = (float(value) for value in metadata[pcd.name])
        min_x, min_y, max_x, max_y = xy_bounds(pcd)
        covered = (
            origin_x <= min_x + tolerance
            and origin_y <= min_y + tolerance
            and origin_x + x_resolution >= max_x - tolerance
            and origin_y + y_resolution >= max_y - tolerance
        )
        if not covered:
            raise ValueError(
                f"metadata does not cover PCD bounds for {pcd.name}: "
                f"metadata=[{origin_x}, {origin_y}].."
                f"[{origin_x + x_resolution}, {origin_y + y_resolution}], "
                f"pcd=[{min_x}, {min_y}]..[{max_x}, {max_y}]"
            )
    return len(pcd_files)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Autoware PCD metadata coverage.")
    parser.add_argument("map_dir", type=Path)
    args = parser.parse_args()
    try:
        count = validate(args.map_dir)
    except (KeyError, OSError, TypeError, ValueError, yaml.YAMLError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"[mapping] metadata coverage valid: {count} PCD file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
