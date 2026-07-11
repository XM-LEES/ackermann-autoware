import re
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
    DOCS / "architecture" / "project_architecture.html",
]

FORMAL_DOCS = [*FORMAL_MARKDOWN_DOCS, *ARCHITECTURE_ASSETS]
MARKDOWN_DOCS = [ROOT / "README.md", *FORMAL_MARKDOWN_DOCS]


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
    DOCS / "architecture" / "rc_official_runtime_graph.html",
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


def fenced_bash_blocks(text: str) -> list[str]:
    return re.findall(r"```bash\n(.*?)\n```", text, flags=re.DOTALL)


def markdown_heading_slugs(text: str) -> set[str]:
    slugs: set[str] = set()
    duplicate_counts: dict[str, int] = {}
    in_fence = False
    for line in text.splitlines():
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = re.match(r"^#{1,6}\s+(.+?)\s*#*$", line)
        if not match:
            continue
        heading = match.group(1).replace("`", "").strip().lower()
        slug = re.sub(r"[^\w\s-]", "", heading)
        slug = re.sub(r"\s+", "-", slug).strip("-")
        duplicate_index = duplicate_counts.get(slug, 0)
        duplicate_counts[slug] = duplicate_index + 1
        slugs.add(slug if duplicate_index == 0 else f"{slug}-{duplicate_index}")
    return slugs


def test_docs_are_converged_to_formal_markdown_and_architecture_assets():
    tracked_docs = sorted(path.relative_to(ROOT).as_posix() for path in DOCS.rglob("*") if path.is_file())
    expected_docs = sorted(path.relative_to(ROOT).as_posix() for path in FORMAL_DOCS)

    assert tracked_docs == expected_docs
    for path in REMOVED_DOCS:
        assert not path.exists(), path


def test_local_markdown_links_resolve():
    for document in MARKDOWN_DOCS:
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", read(document)):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            relative_path = target.split("#", 1)[0]
            if relative_path:
                assert (document.parent / relative_path).resolve().exists(), (document, target)


def test_local_markdown_heading_anchors_resolve():
    for document in MARKDOWN_DOCS:
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", read(document)):
            if target.startswith(("http://", "https://", "mailto:")) or "#" not in target:
                continue
            path_part, anchor = target.split("#", 1)
            target_document = (document.parent / path_part).resolve() if path_part else document
            if target_document.suffix != ".md":
                continue
            assert anchor in markdown_heading_slugs(read(target_document)), (document, target)


def test_documented_repository_command_paths_exist():
    command_pattern = re.compile(r"(?<![\w/])\./((?:scripts|tools)/[A-Za-z0-9_./-]+)")

    for document in MARKDOWN_DOCS:
        for relative_path in command_pattern.findall(read(document)):
            relative_path = relative_path.rstrip(".,;:)")
            assert (ROOT / relative_path).exists(), (document, relative_path)


def test_root_readme_points_to_converged_docs_only():
    text = read(ROOT / "README.md")

    required_terms = [
        "docs/development_guide_zh.md",
        "docs/architecture_zh.md",
        "docs/architecture/project_architecture.html",
        "docs/operations/mapping_workflow_zh.md",
        "docs/operations/rc_runbook_zh.md",
        "docs/reference/interfaces_and_calibration_zh.md",
        "scripts/rc/",
        "vehicle_model:=autoracer_rc",
        "sensor_model:=autoracer_rc_sensor_kit",
        "Platform status is versioned per commit",
        "Current revision status",
        "## Runtime Architecture",
        "Official profile composition example",
        "On-car runtime entrypoint",
        "Sensing -> Localization",
        "Perception (available_disabled) -> Planning",
        "VehicleCmdGate -> Project Safety Gate -> Vehicle Adapter -> Chassis",
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

    assert "The active runtime path is the official Autoware launch path" not in text


def test_official_launch_examples_supply_the_required_map_contract():
    docs_with_launch_examples = [ROOT / "README.md", DOCS / "architecture_zh.md"]

    for path in docs_with_launch_examples:
        for block in fenced_bash_blocks(read(path)):
            if "ros2 launch autoware_launch autoware.launch.xml" not in block:
                continue
            assert "map_path:=" in block or "launch_map:=false" in block, path


def test_readme_declares_build_prerequisites_before_the_build_sequence():
    text = read(ROOT / "README.md")
    build_start = text.index("./scripts/install_rosdeps.sh")

    for prerequisite in [
        "ROS 2 Humble",
        "python3-vcstool",
        "python3-rosdep",
        "python3-colcon-common-extensions",
    ]:
        assert prerequisite in text[:build_start], prerequisite


def test_readme_keeps_one_safe_runtime_example_and_delegates_drive_enable_to_runbook():
    text = read(ROOT / "README.md")

    assert text.count("./scripts/rc/rc_start_autoware.sh") == 1
    assert "ENABLE_DRIVE_COMMANDS=true" not in text


def test_development_guide_explains_src_packages_and_continuation_paths():
    text = read(DOCS / "development_guide_zh.md")

    required_terms = [
        "平台开发契约",
        "first-class platform target",
        "Platform status is commit-scoped",
        "active",
        "available",
        "available_disabled",
        "candidate",
        "reference",
        "pending",
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
        "ACTIVE_RUNTIME_PACKAGES",
        "CANDIDATE_PACKAGES",
        "REFERENCE_PACKAGES",
        "文档维护规则",
        "python3 -m pytest test -q",
        "colcon list --names-only",
    ]
    for term in required_terms:
        assert term in text

    assert "按分支区分车型" not in text
    assert "autoracer_bringup" not in text
    assert "feature/official-autoware-launch" not in text


def test_architecture_doc_owns_platform_profile_launch_and_algorithm_boundaries():
    text = read(DOCS / "architecture_zh.md")

    required_terms = [
        "## 项目边界",
        "## 系统主线",
        "## 能力状态",
        "## Profile 装配",
        "Platform runtime status is commit-scoped",
        "## Map 与 Profile",
        "## Sensing 与 Perception",
        "## Localization",
        "## Planning",
        "## Control、Gate 与 Vehicle Feedback",
        "## AD API、System 与 Diagnostics",
        "## 算法扩展边界",
        "## 开发与部署",
        "## 可视化架构",
        "Perception",
        "available_disabled",
        "NDT Scan Matcher",
        "Gyro Odometer",
        "EKF Localizer",
        "VehicleCmdGate",
        "System / Diagnostics",
        "AD API",
        "vehicle_model:=autoracer_rc",
        "sensor_model:=autoracer_rc_sensor_kit",
        "autoracer_rc_description",
        "autoracer_rc_launch",
        "autoracer_rc_sensor_kit_description",
        "autoracer_rc_sensor_kit_launch",
        "autoracer_hooke",
        "autoracer_hooke_sensor_kit",
        "pending",
        "COLCON_IGNORE",
        "not runtime ready",
        "scripts/rc/",
        "scripts/hooke/",
        "scripts/common/",
        "src/external/autoware",
        "candidate",
        "reference",
        "不在 `src/external/autoware` 里做隐形修改",
        "Perception (available_disabled) -> Planning",
        "/vehicle/status/* -> Localization / Control",
    ]
    for term in required_terms:
        assert term in text

    assert text.count("```mermaid") == 0
    assert text.count("```") % 2 == 0
    assert "静态预览图" not in text
    assert "docs/architecture/image.png" not in text
    assert "按分支区分车型" not in text
    assert "## Hooke Platform Path" not in text
    assert "## RC Platform Path" not in text
    assert "Map + Sensing" not in text
    assert "Planning <---------> Perception" not in text


def test_project_architecture_is_direct_open_html_with_platform_and_runtime_views():
    html = read(DOCS / "architecture" / "project_architecture.html")

    required_terms = [
        "<!doctype html>",
        "<svg",
        "Ackermann Autoware Project Architecture",
        'data-view="overview"',
        'data-view="runtime"',
        'data-view="rc"',
        'data-view="deployment"',
        "RC platform",
        "Hooke platform",
        "Shared official Autoware stack",
        "x86 development and mapping",
        "Orin onboard runtime",
        "Localization",
        "Planning",
        "Control",
        "Perception",
        "available_disabled",
        "AD API",
        "System / Diagnostics",
        "Custom algorithm extension",
        "Safety gate",
        "rc_serial_interface",
        "/vehicle/status/*",
        "Vehicle feedback loop",
        'data-detail-id="vehicle-feedback"',
        "aria-selected",
        "data-detail-id",
    ]
    for term in required_terms:
        assert term in html

    assert not (DOCS / "architecture" / "rc_official_runtime_graph.html").exists()
    assert not (DOCS / "architecture" / "rc_official_runtime_graph.mmd").exists()
    assert "https://" not in html
    assert "min-width: 1260px" not in html
    assert "Map + Sensing" not in html
    assert 'data-detail-id="map-sensing"' not in html


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
        "LAUNCH_PERCEPTION=false",
        "Perception 当前关闭",
        "不能声明动态障碍物感知或完整避障能力",
        "/api/operation_mode/enable_autoware_control",
        "/api/operation_mode/change_to_autonomous",
        "只停止该状态文件登记的进程树",
        "低速动态验证",
    ]
    for term in runbook_terms:
        assert term in runbook

    assert "docs/operations/rc_full_chain_execution_zh.md" not in mapping
    assert "docs/operations/rc_full_chain_execution_zh.md" not in runbook
    assert runbook.count("./scripts/rc/rc_start_sensors.sh") == 1
    assert runbook.count("./scripts/rc/rc_start_localization.sh") == 1
    assert runbook.count("./scripts/rc/rc_start_autoware.sh") == 2
    assert not re.search(r"20\d\d-\d\d-\d\d", runbook)


def test_reference_doc_combines_interfaces_and_calibration_facts():
    text = read(DOCS / "reference" / "interfaces_and_calibration_zh.md")

    required_terms = [
        "## 状态定义",
        "## Shared Topic 契约",
        "## RC Active Facts",
        "### LiDAR",
        "### Initial Pose",
        "### UART Adapter",
        "### 车辆参数",
        "## Hooke Target Contract",
        "## Hooke Reference Material",
        "## Shared Frames",
        "active",
        "reference",
        "pending",
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

    assert "official localization 默认消费 `/sensing/lidar/concatenated/pointcloud`" in text
    assert "Hooke launches" not in text
    assert "RC replaces only" not in text
    assert "## 低速标定检查" not in text


def test_formal_docs_do_not_keep_stale_host_or_transition_language():
    combined = combined_formal_docs()

    stale_terms = [
        "树莓派",
        "192.168.1.136",
        "192.168.1.135",
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
        "current development environment",
        "feature/official-autoware-launch",
    ]
    for term in stale_terms:
        assert term not in combined

    for name in OLD_DOC_NAMES:
        assert name not in combined


def test_localization_docs_match_the_official_ndt_gyro_odometer_ekf_chain():
    architecture = read(DOCS / "architecture_zh.md")
    reference = read(DOCS / "reference" / "interfaces_and_calibration_zh.md")

    for term in ["NDT Scan Matcher", "Gyro Odometer", "EKF Localizer", "Stop Filter"]:
        assert term in architecture

    assert "/localization/kinematic_state" in reference
    assert "NDT 直接产生 `kinematic_state`" not in architecture


def test_stable_docs_do_not_embed_machine_paths_or_feature_branch_names():
    stable_docs = [
        ROOT / "README.md",
        DOCS / "architecture_zh.md",
        DOCS / "development_guide_zh.md",
        DOCS / "reference" / "interfaces_and_calibration_zh.md",
    ]
    for path in stable_docs:
        text = read(path)
        assert "/home/" not in text, path
        assert "feature/official-autoware-launch" not in text, path


def test_stale_superpowers_docs_are_removed_from_formal_docs():
    assert not (DOCS / "superpowers").exists()


def test_architecture_html_and_markdown_share_critical_runtime_statuses():
    architecture = read(DOCS / "architecture_zh.md")
    html = read(DOCS / "architecture" / "project_architecture.html")

    shared_statuses = {
        "RC platform": "active",
        "Hooke platform": "pending",
        "Perception": "available_disabled",
    }
    for capability, status in shared_statuses.items():
        assert f"| {capability} | `{status}` |" in architecture

    assert '"rc-profile": ["active"' in html
    assert '"hooke-profile": ["pending"' in html
    assert '"perception": ["available_disabled"' in html
