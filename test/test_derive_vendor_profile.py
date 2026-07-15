from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
DERIVER = ROOT / "scripts" / "vendor" / "derive_profile.py"


def _package(path: Path, name: str, dependencies=()):
    path.mkdir(parents=True)
    dependency_xml = "".join(f"<depend>{dependency}</depend>" for dependency in dependencies)
    (path / "package.xml").write_text(
        f"<package format='3'><name>{name}</name><version>0.0.0</version>"
        f"<description>x</description><maintainer email='x@y.z'>x</maintainer>"
        f"<license>Apache-2.0</license>{dependency_xml}</package>",
        encoding="utf-8",
    )


def test_derives_transitive_vendor_closure_in_catalog_order(tmp_path):
    source = tmp_path / "source"
    product = tmp_path / "product"
    _package(product / "app", "app", ("vendor_a", "system_dep"))
    _package(source / "repo" / "a", "vendor_a", ("vendor_b",))
    _package(source / "repo" / "b", "vendor_b")
    catalog = tmp_path / "packages.tsv"
    catalog.write_text("vendor_b\trepo/b\nvendor_a\trepo/a\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(DERIVER),
            "--source-root",
            str(source),
            "--product-root",
            str(product),
            "--catalog",
            str(catalog),
        ],
        text=True,
        capture_output=True,
        check=True,
    )

    assert result.stdout.splitlines() == ["vendor_b", "vendor_a"]


def test_refuses_to_lock_a_closure_when_selected_source_is_missing(tmp_path):
    product = tmp_path / "product"
    _package(product / "app", "app", ("vendor_a",))
    catalog = tmp_path / "packages.tsv"
    catalog.write_text("vendor_a\trepo/a\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(DERIVER),
            "--source-root",
            str(tmp_path / "source"),
            "--product-root",
            str(product),
            "--catalog",
            str(catalog),
        ],
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert result.stdout == ""
    assert "missing package.xml for vendor_a" in result.stderr


def test_test_dependencies_do_not_enter_the_runtime_closure(tmp_path):
    source = tmp_path / "source"
    product = tmp_path / "product"
    app = product / "app"
    _package(app, "app", ("vendor_a",))
    package_xml = (app / "package.xml").read_text(encoding="utf-8")
    (app / "package.xml").write_text(
        package_xml.replace("</package>", "<test_depend>vendor_test</test_depend></package>"),
        encoding="utf-8",
    )
    _package(source / "repo" / "a", "vendor_a")
    _package(source / "repo" / "test", "vendor_test")
    catalog = tmp_path / "packages.tsv"
    catalog.write_text("vendor_a\trepo/a\nvendor_test\trepo/test\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(DERIVER),
            "--source-root",
            str(source),
            "--product-root",
            str(product),
            "--catalog",
            str(catalog),
        ],
        text=True,
        capture_output=True,
        check=True,
    )

    assert result.stdout.splitlines() == ["vendor_a"]


def test_combines_core_and_selected_platform_product_roots(tmp_path):
    source = tmp_path / "source"
    core = tmp_path / "core"
    platform = tmp_path / "platform"
    _package(core / "core_app", "core_app", ("vendor_a",))
    _package(platform / "platform_app", "platform_app", ("vendor_b",))
    _package(source / "repo" / "a", "vendor_a")
    _package(source / "repo" / "b", "vendor_b")
    catalog = tmp_path / "packages.tsv"
    catalog.write_text("vendor_a\trepo/a\nvendor_b\trepo/b\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(DERIVER),
            "--source-root",
            str(source),
            "--product-root",
            str(core),
            "--product-root",
            str(platform),
            "--catalog",
            str(catalog),
        ],
        text=True,
        capture_output=True,
        check=True,
    )

    assert result.stdout.splitlines() == ["vendor_a", "vendor_b"]
