from pathlib import Path


def _repository_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "src" / "core").is_dir():
            return parent
    raise RuntimeError("repository root not found")


REPOSITORY_ROOT = _repository_root()
CORE_ROOT = REPOSITORY_ROOT / "src" / "core"
FORBIDDEN_CORE_TOKENS = (
    "hooke2",
    "fixposition",
    "pandar",
    "nebula",
    "lslidar",
    "hipnuc",
    "rc_serial",
    "safe_control_cmd",
)


def _product_sources(root: Path) -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in root.rglob("*")
        if path.suffix in {".py", ".xml", ".yaml", ".yml"}
        and "test" not in path.parts
    ).lower()


def test_core_sources_have_no_platform_tokens():
    sources = _product_sources(CORE_ROOT)

    for token in FORBIDDEN_CORE_TOKENS:
        assert token not in sources


def test_core_manifests_do_not_depend_on_platform_packages():
    manifests = "\n".join(
        path.read_text(encoding="utf-8")
        for path in CORE_ROOT.glob("*/package.xml")
    ).lower()

    assert "autoracer_hooke2" not in manifests
    assert "autoracer_rc" not in manifests
    assert "hooke2_" not in manifests


def test_course_map_rviz_is_inspection_only():
    launch = (
        CORE_ROOT / "autoracer_bringup" / "launch" / "course_map_rviz.launch.py"
    )
    config = CORE_ROOT / "autoracer_bringup" / "rviz" / "course_map.rviz"

    assert launch.is_file()
    assert config.is_file()
    source = launch.read_text(encoding="utf-8")
    for executable in (
        "pcd_to_pointcloud",
        "fixed_course_publisher",
        "rviz2",
    ):
        assert f'executable="{executable}"' in source
    for forbidden in (
        "lanelet",
        "localization.launch",
        "local_trajectory_planner",
        "autoracer_control",
        "autoracer_safety",
        "autoracer_sensing",
        "autoracer_rc",
        "autoracer_hooke2",
    ):
        assert forbidden not in source.lower()
    rviz = config.read_text(encoding="utf-8")
    assert "/map/pointcloud_map" in rviz
    assert "/planning/course_markers" in rviz


def test_shared_race_exposes_platform_parameter_contract():
    race_source = (CORE_ROOT / "autoracer_bringup" / "launch" / "race.launch.py").read_text(
        encoding="utf-8"
    )
    planning_source = (
        CORE_ROOT / "autoracer_bringup" / "launch" / "planning.launch.py"
    ).read_text(encoding="utf-8")
    planner_source = (
        CORE_ROOT
        / "autoracer_planning"
        / "launch"
        / "fixed_course_planning.launch.py"
    ).read_text(encoding="utf-8")
    localization_source = (
        CORE_ROOT / "autoracer_localization" / "launch" / "localization.launch.py"
    ).read_text(encoding="utf-8")

    for argument in (
        "vehicle_info_param_file",
        "control_param_file",
        "gate_param_file",
        "runtime_param_file",
        "max_speed_mps",
        "max_accel_mps2",
        "max_decel_mps2",
        "command_latency_sec",
        "stopping_margin_m",
        "gnss_enabled",
        "initial_pose",
    ):
        assert f'LaunchConfiguration("{argument}")' in race_source

    for argument in (
        "max_accel_mps2",
        "max_decel_mps2",
        "command_latency_sec",
        "stopping_margin_m",
    ):
        assert f'LaunchConfiguration("{argument}")' in planning_source
        assert f'LaunchConfiguration("{argument}")' in planner_source

    for argument in ("gnss_enabled", "initial_pose"):
        assert f'LaunchConfiguration("{argument}")' in planning_source
        assert f'LaunchConfiguration("{argument}")' in localization_source
