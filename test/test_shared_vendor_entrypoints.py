from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def test_import_and_vendor_build_use_the_shared_profile_resolver():
    for name in ("import_dependencies.sh", "build_vendor.sh"):
        source = (SCRIPTS / name).read_text(encoding="utf-8")
        assert "vendor/resolve_dependencies.py" in source
        assert "AUTORACER_PROFILE:-hooke2" in source


def test_default_orchestration_remains_hooke_and_rc_requires_explicit_selection():
    product = (SCRIPTS / "build_product.sh").read_text(encoding="utf-8")
    assert "AUTORACER_PROFILE:-hooke2" in product
    assert "hooke2)" in product
    assert "rc)" in product
    assert "all)" not in product
    assert "AUTORACER_VENDOR_WS is required for non-Hooke profile" in product


def test_rc_does_not_own_a_second_dependency_pipeline():
    legacy_directory = ROOT / "src" / "platform" / "rc" / "dependencies"

    assert not legacy_directory.exists()


def test_repository_revision_has_one_authoritative_file():
    assert (ROOT / "dependencies" / "autoracer.repos").is_file()
    assert not (ROOT / "dependencies" / "versions.lock.yaml").exists()


def test_rosdep_uses_only_the_selected_platform_product_tree():
    source = (SCRIPTS / "install_rosdeps.sh").read_text(encoding="utf-8")

    assert "AUTORACER_PROFILE:-hooke2" in source
    assert '"${ROOT_DIR}/src/core"' in source
    assert '"${ROOT_DIR}/src/platform/hooke2"' in source
    assert '"${ROOT_DIR}/src/platform/rc"' in source
    assert '"${ROOT_DIR}/src"' not in source
