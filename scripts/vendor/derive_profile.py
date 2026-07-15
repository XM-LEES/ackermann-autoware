#!/usr/bin/env python3
"""Derive a vendor closure from product and fixed-source package manifests."""

from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


DEPENDENCY_TAGS = {
    "depend",
    "build_depend",
    "build_export_depend",
    "buildtool_depend",
    "buildtool_export_depend",
    "exec_depend",
}


class DerivationError(ValueError):
    pass


def read_catalog(path: Path) -> list[tuple[str, str]]:
    records: list[tuple[str, str]] = []
    names: set[str] = set()
    paths: set[str] = set()
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        fields = raw.split("\t")
        if len(fields) != 2 or not all(fields):
            raise DerivationError(f"invalid catalog record at {path}:{number}")
        name, package_path = fields
        if name in names or package_path in paths:
            raise DerivationError(f"duplicate catalog record at {path}:{number}")
        names.add(name)
        paths.add(package_path)
        records.append((name, package_path))
    return records


def read_manifest(path: Path, expected_name: str | None = None) -> tuple[str, set[str]]:
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as error:
        raise DerivationError(f"invalid package manifest {path}: {error}") from error
    name = (root.findtext("name") or "").strip()
    if not name:
        raise DerivationError(f"package manifest has no name: {path}")
    if expected_name is not None and name != expected_name:
        raise DerivationError(
            f"package name mismatch at {path}: expected {expected_name}, found {name}"
        )
    dependencies = {
        (element.text or "").strip()
        for element in root
        if element.tag in DEPENDENCY_TAGS and (element.text or "").strip()
    }
    return name, dependencies


def derive(source_root: Path, product_roots: list[Path], catalog_path: Path):
    catalog = read_catalog(catalog_path)
    paths = dict(catalog)
    vendor_names = set(paths)
    product_manifests = sorted(
        manifest for product_root in product_roots for manifest in product_root.rglob("package.xml")
    )
    if not product_manifests:
        raise DerivationError("no product package.xml files below selected product roots")

    product_packages: set[str] = set()
    product_dependencies: dict[str, set[str]] = {}
    for manifest in product_manifests:
        name, dependencies = read_manifest(manifest)
        if name in product_packages:
            raise DerivationError(f"duplicate product package name: {name}")
        product_packages.add(name)
        product_dependencies[name] = dependencies

    roots = {
        dependency
        for dependencies in product_dependencies.values()
        for dependency in dependencies
        if dependency in vendor_names
    }
    queue = deque(sorted(roots))
    selected: set[str] = set()
    edges: list[tuple[str, str]] = []
    for product, dependencies in sorted(product_dependencies.items()):
        edges.extend((product, dependency) for dependency in sorted(dependencies & vendor_names))

    while queue:
        name = queue.popleft()
        if name in selected:
            continue
        package_xml = source_root / paths[name] / "package.xml"
        if not package_xml.is_file():
            raise DerivationError(f"missing package.xml for {name}: {package_xml}")
        _, dependencies = read_manifest(package_xml, name)
        selected.add(name)
        for dependency in sorted(dependencies & vendor_names):
            edges.append((name, dependency))
            if dependency not in selected:
                queue.append(dependency)

    ordered = [name for name, _ in catalog if name in selected]
    return ordered, edges


def main() -> int:
    default_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--product-root", type=Path, action="append")
    parser.add_argument(
        "--catalog", type=Path, default=default_root / "dependencies" / "vendor-packages.tsv"
    )
    parser.add_argument("--format", choices=("names", "edges"), default="names")
    args = parser.parse_args()
    try:
        product_roots = args.product_root or [default_root / "src"]
        names, edges = derive(args.source_root, product_roots, args.catalog)
    except (OSError, DerivationError) as error:
        print(f"vendor profile derivation failed: {error}", file=sys.stderr)
        return 2
    if args.format == "names":
        print("\n".join(names))
    else:
        print("\n".join(f"{source}\t{target}" for source, target in edges))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
