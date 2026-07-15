from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
RESOLVER = ROOT / "scripts" / "vendor" / "resolve_dependencies.py"


def _resolve(output_format):
    return subprocess.run(
        [sys.executable, str(RESOLVER), "--profile", "hooke2", "--format", output_format],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.splitlines()


def test_hooke_default_inventory_matches_carmaker_validated_pilot_baseline():
    packages = _resolve("names")
    repositories = _resolve("repository-paths")

    assert len(packages) == 99
    assert len(repositories) == 14
    assert "hipnuc_imu" not in packages
    assert "lslidar_driver" not in packages
    assert "vendor/lslidar_ros2" not in repositories
    assert "vendor/hipnuc_products" not in repositories


def test_hooke_is_the_resolver_default_profile():
    explicit = _resolve("records")
    implicit = subprocess.run(
        [sys.executable, str(RESOLVER), "--format", "records"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.splitlines()

    assert implicit == explicit
