from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


FORMAL_MARKDOWN_DOCS = [
    DOCS / "development_guide_zh.md",
    DOCS / "architecture_zh.md",
    DOCS / "operations" / "rc_runbook_zh.md",
    DOCS / "operations" / "mapping_workflow_zh.md",
    DOCS / "reference" / "interfaces_and_calibration_zh.md",
]

ARCHITECTURE_ASSETS = [
    DOCS / "architecture" / "rc_official_runtime_graph.html",
]

FORMAL_DOCS = [*FORMAL_MARKDOWN_DOCS, *ARCHITECTURE_ASSETS]


REMOVED_DOCS = [
    DOCS / "README_zh.md",
    DOCS / "architecture" / "image.png",
    DOCS / "architecture" / "platform_and_stack_zh.md",
    DOCS / "architecture" / "profile_matrix_zh.md",
    DOCS / "architecture" / "official_launch_structure_zh.md",
    DOCS / "architecture" / "official_migration_zh.md",
    DOCS / "architecture" / "runtime_alignment_audit_zh.md",
    DOCS / "operations" / "rc_full_chain_execution_zh.md",
    DOCS / "reference" / "interfaces_and_topics_zh.md",
    DOCS / "reference" / "calibration_zh.md",
    DOCS / "architecture_visualization_zh.md",
    DOCS / "architecture" / "generated" / "rc_official_runtime_graph.mmd",
    DOCS / "architecture" / "rc_official_runtime_graph.mmd",
]


OLD_DOC_NAMES = [
    "rc_hooke_platform_boundary_zh.md",
    "rc_run_readiness_checklist_zh.md",
    "rc_autoware_full_workflow_zh.md",
    "autoracer_hooke_chain_audit",
    "rc_official_autoware_diff_audit_zh.md",
    "sensing_feedback_topics.md",
    "hooke2_chassis_chain.md",
    "calibration_checklist.md",
    "minimal_stack.md",
]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def combined_formal_docs() -> str:
    return "\n".join(read(path) for path in FORMAL_MARKDOWN_DOCS)


def test_docs_are_converged_to_formal_markdown_and_architecture_assets():
    tracked_docs = sorted(path.relative_to(ROOT).as_posix() for path in DOCS.rglob("*") if path.is_file())
    expected_docs = sorted(path.relative_to(ROOT).as_posix() for path in FORMAL_DOCS)

    assert tracked_docs == expected_docs
    for path in REMOVED_DOCS:
        assert not path.exists(), path


def test_root_readme_points_to_converged_docs_only():
    text = read(ROOT / "README.md")

    required_terms = [
        "docs/development_guide_zh.md",
        "docs/architecture_zh.md",
        "docs/architecture/rc_official_runtime_graph.html",
        "docs/operations/mapping_workflow_zh.md",
        "docs/operations/rc_runbook_zh.md",
        "docs/reference/interfaces_and_calibration_zh.md",
        "scripts/rc/",
        "vehicle_model:=autoracer_rc",
        "sensor_model:=autoracer_rc_sensor_kit",
        "Platform status is versioned per commit",
        "Current branch status",
    ]
    for term in required_terms:
        assert term in text

    removed_refs = [path.relative_to(DOCS).as_posix() for path in REMOVED_DOCS]
    stale_or_local_terms = [
        *removed_refs,
        "/home/",
        "pilot-auto.x1",
        "IMPORT_FROM_PILOT",
        "rc_mapping_ws",
        "autoracer_maps",
    ]
    for term in stale_or_local_terms:
        assert term not in text


def test_development_guide_explains_src_packages_and_continuation_paths():
    text = read(DOCS / "development_guide_zh.md")

    required_terms = [
        "平台开发契约",
        "feature/official-autoware-launch",
        "first-class platform target",
        "Platform status is commit-scoped",
        "Current branch status",
        "active platform profile",
        "integration pending",
        "upstream/pinned dependency",
        "local algorithm package",
        "src/autoracer_rc_description",
        "src/autoracer_rc_launch",
        "src/autoracer_rc_sensor_kit_description",
        "src/autoracer_rc_sensor_kit_launch",
        "src/autoracer_hooke_description",
        "src/hooke2_vehicle",
        "src/autoracer_vehicle_interface",
        "src/autoracer_sensing",
        "src/autoracer_localization",
        "src/autoracer_planning",
        "src/autoracer_control",
        "新增或修改平台 Profile",
        "底盘 Adapter",
        "自研算法模块",
        "文档维护规则",
        "python3 -m pytest test -q",
        "colcon list --names-only",
    ]
    for term in required_terms:
        assert term in text

    assert "按分支区分车型" not in text
    assert "autoracer_bringup" not in text


def test_architecture_doc_owns_platform_profile_launch_and_algorithm_boundaries():
    text = read(DOCS / "architecture_zh.md")

    required_terms = [
        "## 系统边界",
        "## Profile 装配",
        "## 平台状态",
        "Platform runtime status is commit-scoped",
        "## Nodeviewer/Dataflow",
        "## Shared Autoware Stack",
        "## Hooke Platform Path",
        "## RC Platform Path",
        "Shared official Autoware upper stack",
        "vehicle_model:=autoracer_rc",
        "sensor_model:=autoracer_rc_sensor_kit",
        "autoracer_rc_description",
        "autoracer_rc_launch",
        "autoracer_rc_sensor_kit_description",
        "autoracer_rc_sensor_kit_launch",
        "autoracer_hooke",
        "autoracer_hooke_sensor_kit",
        "disabled_placeholder",
        "COLCON_IGNORE",
        "not runtime ready",
        "scripts/rc/",
        "scripts/hooke/",
        "scripts/common/",
        "src/external/autoware",
        "自研 planning/control 候选",
        "不在 `src/external/autoware` 里做隐形修改",
    ]
    for term in required_terms:
        assert term in text

    assert text.count("```mermaid") == 2
    assert text.count("```") % 2 == 0
    assert "静态预览图" not in text
    assert "docs/architecture/image.png" not in text
    assert "按分支区分车型" not in text


def test_architecture_graph_is_direct_open_html_not_mermaid_source():
    html = read(DOCS / "architecture" / "rc_official_runtime_graph.html")

    required_terms = [
        "<!doctype html>",
        "<svg",
        "RC Official Autoware Runtime Graph",
        "nodeviewer-style",
        "RViz2",
        "Foxglove",
        "NDT localization",
        "Official control",
        "Safety gate",
        "rc_serial_interface",
        "/vehicle/status/*",
    ]
    for term in required_terms:
        assert term in html

    assert not (DOCS / "architecture" / "rc_official_runtime_graph.mmd").exists()
    assert "https://" not in html


def test_runtime_docs_default_to_official_planning_control_boundary():
    current_runtime_docs = "\n".join(
        (
            read(DOCS / "architecture_zh.md"),
            read(DOCS / "operations" / "rc_runbook_zh.md"),
            read(DOCS / "reference" / "interfaces_and_calibration_zh.md"),
        )
    )

    required_terms = [
        "official Autoware planning/control",
        "自研 planning/control 候选",
        "/control/command/control_cmd",
        "/autoracer/control/safe_control_cmd",
        "/sensing/vehicle_velocity_converter/twist_with_covariance",
        "rc_serial_interface",
        "command_gate",
    ]
    for term in required_terms:
        assert term in current_runtime_docs

    stale_default_terms = [
        "lanelet_route_planner",
        "pure_pursuit_controller",
        "/autoracer/control/raw_control_cmd",
    ]
    for term in stale_default_terms:
        assert term not in current_runtime_docs


def test_operations_docs_preserve_mapping_and_runtime_sequences():
    mapping = read(DOCS / "operations" / "mapping_workflow_zh.md")
    runbook = read(DOCS / "operations" / "rc_runbook_zh.md")

    mapping_terms = [
        "车端采集",
        "Foxglove Bridge",
        "Super-LIO",
        "Autoware 地图目录",
        "pointcloud_map.pcd",
        "pointcloud_map_metadata.yaml",
        "lanelet2_map.osm",
        "map_projector_info.yaml",
        "/sensing/lidar/raw/pointcloud",
        "/sensing/lidar/concatenated/pointcloud",
        "/sensing/imu/imu_data_raw",
        "/tf_static",
    ]
    for term in mapping_terms:
        assert term in mapping

    runbook_terms = [
        "可复制启动命令",
        "不要把 localization-only 和 full-chain 连续叠加启动",
        "/initialpose` 是 RViz 操作入口",
        "/initialpose3d` 是 official localization 内部入口",
        "配置 LiDAR 网口",
        "启动 sensors",
        "NDT",
        "export MAP_NAME=floor1_mapping_001",
        "rc_start_localization.sh",
        "rc_start_autoware.sh",
        "/planning/trajectory",
        "/control/command/control_cmd",
        "/autoracer/control/safe_control_cmd",
        "ENABLE_DRIVE_COMMANDS=false",
        "不要用 `timeout -s INT`",
        "低速动态验证",
    ]
    for term in runbook_terms:
        assert term in runbook

    assert "docs/operations/rc_full_chain_execution_zh.md" not in mapping
    assert "docs/operations/rc_full_chain_execution_zh.md" not in runbook


def test_reference_doc_combines_interfaces_and_calibration_facts():
    text = read(DOCS / "reference" / "interfaces_and_calibration_zh.md")

    required_terms = [
        "## Topic 契约",
        "## LiDAR",
        "## Fixposition 与 Initial Pose",
        "## Hooke2 CAN Adapter",
        "## RC UART Adapter",
        "## RC 车辆参数",
        "## Frames",
        "## 低速标定检查",
        "192.168.1.102",
        "192.168.1.200",
        "/sensing/lidar/raw/pointcloud",
        "/sensing/lidar/concatenated/pointcloud",
        "/sensing/lidar/filtered/pointcloud",
        "/vehicle/status/velocity_status",
        "0.6 m",
        "0.262 rad",
    ]
    for term in required_terms:
        assert term in text

    assert "runtime localization consumes the official default concatenated topic" in text


def test_formal_docs_do_not_keep_stale_host_or_transition_language():
    combined = combined_formal_docs()

    stale_terms = [
        "树莓派",
        "192.168.1.136",
        "rc-car-migration",
        "/home/corage/workspace/project/autoracer-hooke",
        "raw control",
        "/autoracer/control/raw_control_cmd",
        "后续实现计划",
        "rc_full_chain_execution_zh.md",
        "runtime_alignment_audit_zh.md",
        "official_launch_structure_zh.md",
        "official_migration_zh.md",
        "profile_matrix_zh.md",
        "platform_and_stack_zh.md",
        "reference/interfaces_and_topics_zh.md",
        "reference/calibration_zh.md",
        "当前唯一可运行基线",
        "RC 是 Hooke",
        "验证 Hooke",
        "给旧框架开发者",
        "旧框架是",
        "新框架是",
        "以后怎么判断",
        "如何理解",
        "交给 Hooke 负责人",
        "未来 Hooke",
        "当前 ARM 车辆主机是临时",
    ]
    for term in stale_terms:
        assert term not in combined

    for name in OLD_DOC_NAMES:
        assert name not in combined


def test_current_phase_does_not_describe_future_state_fusion():
    combined = combined_formal_docs()
    forbidden_terms = ["卡尔曼", "Kalman", "EKF", "ekf"]
    for term in forbidden_terms:
        assert term not in combined


def test_stale_superpowers_docs_are_removed_from_formal_docs():
    assert not (DOCS / "superpowers").exists()
