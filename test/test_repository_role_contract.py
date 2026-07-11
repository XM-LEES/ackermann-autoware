import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_project_package_metadata_uses_current_roles_not_legacy_runtime_claims():
    metadata = {
        "autoracer_control": "candidate",
        "autoracer_planning": "candidate",
        "autoracer_localization": "candidate",
        "autoracer_sensing": "sensor adapter",
        "autoracer_safety": "safety gate",
        "autoracer_description": "reference",
    }
    forbidden = ["Hooke2 vehicle output", "Minimal sensing adapters", "closed-track Autoracer"]

    for package, required in metadata.items():
        package_xml = read(ROOT / "src" / package / "package.xml")
        setup_py = ROOT / "src" / package / "setup.py"
        combined = package_xml + (read(setup_py) if setup_py.exists() else "")
        assert required.lower() in combined.lower(), package
        for term in forbidden:
            assert term not in combined, package


def test_build_script_names_active_candidate_and_reference_groups():
    build = read(ROOT / "scripts" / "build_minimal.sh")

    for group in ["ACTIVE_RUNTIME_PACKAGES", "CANDIDATE_PACKAGES", "REFERENCE_PACKAGES"]:
        assert group in build
    for package in ["autoracer_rc_launch", "autoracer_planning", "autoracer_description"]:
        assert package in build
    assert 'PACKAGES=("${ACTIVE_RUNTIME_PACKAGES[@]}")' in build
    assert 'BUILD_CANDIDATES:-false' in build
    assert 'BUILD_REFERENCES:-false' in build


def test_minimal_build_selects_optional_groups_only_when_requested(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    call_log = tmp_path / "colcon.log"
    fake_colcon = fake_bin / "colcon"
    fake_colcon.write_text(
        "#!/usr/bin/env bash\n"
        'printf \'%s\\n\' "$*" >"${COLCON_CALL_LOG}"\n'
    )
    fake_colcon.chmod(0o755)

    base_env = os.environ.copy()
    base_env.update(
        {
            "AUTORACER_SOURCE_LOCAL_SETUP": "false",
            "COLCON_CALL_LOG": str(call_log),
            "PATH": f"{fake_bin}:{base_env['PATH']}",
        }
    )

    default_result = subprocess.run(
        ["bash", "scripts/build_minimal.sh"],
        cwd=ROOT,
        env=base_env,
        text=True,
        capture_output=True,
        timeout=8,
        check=False,
    )
    assert default_result.returncode == 0, default_result.stderr
    default_call = call_log.read_text()
    assert "autoracer_rc_launch" in default_call
    assert "autoracer_planning" not in default_call
    assert "autoracer_description" not in default_call

    optional_env = base_env | {"BUILD_CANDIDATES": "true", "BUILD_REFERENCES": "true"}
    optional_result = subprocess.run(
        ["bash", "scripts/build_minimal.sh"],
        cwd=ROOT,
        env=optional_env,
        text=True,
        capture_output=True,
        timeout=8,
        check=False,
    )
    assert optional_result.returncode == 0, optional_result.stderr
    optional_call = call_log.read_text()
    assert "autoracer_planning" in optional_call
    assert "autoracer_description" in optional_call


def test_normal_checkout_does_not_reimport_vendored_dependencies():
    readme = read(ROOT / "README.md")

    assert not (ROOT / "scripts" / "import_dependencies.sh").exists()
    assert "./scripts/import_dependencies.sh" not in readme
    assert "IMPORT_FROM_PILOT" not in "\n".join(
        read(path) for path in (ROOT / "scripts").rglob("*") if path.is_file()
    )
    assert not (ROOT / "scripts" / "build_bench.sh").exists()


def test_runtime_defaults_do_not_duplicate_profile_or_map_configuration():
    defaults = read(ROOT / "defaults.env")

    for stale_name in ["whale_map_20251107", "MAP_RVIZ_LEAF_SIZE", "WHEEL_BASE_M", "MAX_STEER_RAD"]:
        assert stale_name not in defaults


def test_ros_environment_has_no_hard_coded_pilot_underlay():
    ros_env = read(ROOT / "scripts" / "ros_env.sh")

    assert "/home/corage" not in ros_env
    assert "pilot-auto.x1" not in ros_env
    assert "AUTORACER_BLOCKED_UNDERLAY" in ros_env


def test_ros_environment_removes_inherited_workspace_underlay_by_default(tmp_path):
    stale_underlay = tmp_path / "stale_ws" / "install"
    env = os.environ.copy()
    env.update(
        {
            "AMENT_PREFIX_PATH": f"{stale_underlay}:/opt/ros/humble",
            "COLCON_PREFIX_PATH": str(stale_underlay),
            "CMAKE_PREFIX_PATH": f"{stale_underlay}:/opt/ros/humble",
            "LD_LIBRARY_PATH": f"{stale_underlay}/lib:/usr/lib",
            "PYTHONPATH": f"{stale_underlay}/python:/usr/lib/python3/dist-packages",
            "PATH": f"{stale_underlay}/bin:{env['PATH']}",
            "AUTORACER_SOURCE_LOCAL_SETUP": "false",
        }
    )
    result = subprocess.run(
        [
            "bash",
            "-c",
            "source scripts/ros_env.sh && "
            "printf '%s\\n' \"$AMENT_PREFIX_PATH\" \"${COLCON_PREFIX_PATH:-}\" "
            "\"$CMAKE_PREFIX_PATH\" \"$LD_LIBRARY_PATH\" \"$PYTHONPATH\" \"$PATH\"",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=8,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert str(stale_underlay) not in result.stdout


def test_rosdep_installer_fails_with_actionable_initialization_command():
    installer = read(ROOT / "scripts" / "install_rosdeps.sh")
    readme = read(ROOT / "README.md")

    assert "ROSDEP_SOURCES_LIST" in installer
    assert "sudo rosdep init" in installer
    assert "sudo rosdep init" in readme


def test_mapping_helpers_do_not_advertise_stale_machine_addresses_or_topics():
    sync_script = read(ROOT / "tools" / "mapping" / "sync_map_to_vehicle.sh")
    record_script = read(ROOT / "scripts" / "record_mapping_bag.sh")

    assert "192.168.1.135" not in sync_script
    assert "/scan_raw" not in record_script


def test_mapping_helpers_use_portable_repo_relative_defaults():
    helpers = [
        ROOT / "scripts" / "pull_mapping_bag.sh",
        ROOT / "tools" / "mapping" / "bootstrap_mapping_ws.sh",
        ROOT / "tools" / "mapping" / "run_super_lio_offline.sh",
        ROOT / "tools" / "mapping" / "prepare_autoware_pointcloud_map.sh",
        ROOT / "tools" / "mapping" / "sync_map_to_vehicle.sh",
    ]

    for path in helpers:
        assert "/home/milesli" not in read(path), path

    combined = "\n".join(read(path) for path in helpers)
    assert "rc_mapping_ws" in combined
    assert "rc_mapping_data" in combined


def test_hooke_placeholders_use_the_shared_pending_status_vocabulary():
    readmes = [
        ROOT / "src" / "autoracer_hooke_description" / "README.md",
        ROOT / "src" / "autoracer_hooke_launch" / "README.md",
        ROOT / "src" / "autoracer_hooke_sensor_kit_description" / "README.md",
        ROOT / "src" / "autoracer_hooke_sensor_kit_launch" / "README.md",
    ]

    for path in readmes:
        text = read(path)
        assert "Status: `pending`." in text, path
        assert "target Hooke platform" in text, path
        assert "disabled_placeholder" not in text, path
        assert "future Hooke" not in text, path

    for readme in readmes:
        requirements = read(readme.with_name("profile_requirements.yaml"))
        assert "status: pending" in requirements, readme.parent
        assert "not_runtime_ready: true" in requirements, readme.parent
        assert "disabled_placeholder" not in requirements, readme.parent

    launcher = read(ROOT / "scripts" / "run_official_autoware.sh")
    assert "Hooke is currently pending" in launcher
    assert "disabled_placeholder" not in launcher
