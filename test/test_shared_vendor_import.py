import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
IMPORTER = ROOT / "scripts" / "import_dependencies.sh"
RESOLVER = ROOT / "scripts" / "vendor" / "resolve_dependencies.py"


def _names(profile):
    return subprocess.run(
        [sys.executable, str(RESOLVER), "--profile", profile, "--format", "names"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout


def _fake_colcon(tmp_path, output):
    binary = tmp_path / "bin" / "colcon"
    binary.parent.mkdir()
    binary.write_text("#!/usr/bin/env bash\nprintf '%s' \"$FAKE_COLCON_OUTPUT\"\n", encoding="utf-8")
    binary.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = f"{binary.parent}:{environment['PATH']}"
    environment["FAKE_COLCON_OUTPUT"] = output
    return environment


def test_verify_only_accepts_the_exact_resolved_rc_set(tmp_path):
    workspace = tmp_path / "rc-vendor-ws"
    (workspace / "src").mkdir(parents=True)
    expected = _names("rc")
    environment = _fake_colcon(tmp_path, expected)
    environment.update(AUTORACER_PROFILE="rc", AUTORACER_VENDOR_WS=str(workspace))

    result = subprocess.run(
        [str(IMPORTER), "--verify-only"],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    expected_count = len(expected.splitlines())
    assert f"verified vendor package set: {expected_count} packages" in result.stdout


def test_verify_only_rejects_a_stale_package(tmp_path):
    workspace = tmp_path / "rc-vendor-ws"
    (workspace / "src").mkdir(parents=True)
    environment = _fake_colcon(tmp_path, _names("rc") + "stale_package\n")
    environment.update(AUTORACER_PROFILE="rc", AUTORACER_VENDOR_WS=str(workspace))

    result = subprocess.run(
        [str(IMPORTER), "--verify-only"],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "differs from profile rc" in result.stderr


def test_rc_import_never_falls_back_to_the_hooke_workspace():
    environment = os.environ.copy()
    environment["AUTORACER_PROFILE"] = "rc"
    environment.pop("AUTORACER_VENDOR_WS", None)

    result = subprocess.run(
        [str(IMPORTER), "--verify-only"],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 2
    assert "AUTORACER_VENDOR_WS is required" in result.stderr
