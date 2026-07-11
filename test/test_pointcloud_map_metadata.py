import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "tools" / "mapping" / "validate_pointcloud_metadata.py"


def _write_map(map_dir: Path, x_resolution: float, y_resolution: float) -> None:
    map_dir.mkdir()
    (map_dir / "pointcloud_map.pcd").write_text(
        "\n".join(
            [
                "# .PCD v0.7",
                "VERSION 0.7",
                "FIELDS x y z intensity",
                "SIZE 4 4 4 4",
                "TYPE F F F F",
                "COUNT 1 1 1 1",
                "WIDTH 2",
                "HEIGHT 1",
                "POINTS 2",
                "DATA ascii",
                "-42.6 -68.4 0.0 1.0",
                "262.2 126.6 0.0 1.0",
            ]
        )
        + "\n"
    )
    (map_dir / "pointcloud_map_metadata.yaml").write_text(
        yaml.safe_dump(
            {
                "pointcloud_map.pcd": [-43, -69],
                "x_resolution": x_resolution,
                "y_resolution": y_resolution,
            },
            sort_keys=False,
        )
    )


def test_metadata_validator_accepts_bounds_covering_single_pcd(tmp_path):
    map_dir = tmp_path / "valid_map"
    _write_map(map_dir, x_resolution=306.0, y_resolution=196.0)

    result = subprocess.run(
        [sys.executable, str(VALIDATOR), str(map_dir)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "metadata coverage valid" in result.stdout


def test_metadata_validator_rejects_bounds_smaller_than_single_pcd(tmp_path):
    map_dir = tmp_path / "invalid_map"
    _write_map(map_dir, x_resolution=100.0, y_resolution=100.0)

    result = subprocess.run(
        [sys.executable, str(VALIDATOR), str(map_dir)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "does not cover PCD bounds" in result.stderr
