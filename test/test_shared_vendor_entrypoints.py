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
