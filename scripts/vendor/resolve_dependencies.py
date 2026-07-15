#!/usr/bin/env python3
"""Resolve a platform profile from the repository's pinned vendor catalog."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import re
import sys


ROOT = Path(__file__).resolve().parents[2]
DEPENDENCIES = ROOT / "dependencies"
PACKAGE_NAME = re.compile(r"[a-z][a-z0-9_]*\Z")
PROFILE_NAME = re.compile(r"[a-z][a-z0-9_]*\Z")


class ResolutionError(ValueError):
    pass


@dataclass(frozen=True)
class Repository:
    path: str
    url: str
    revision: str


@dataclass(frozen=True)
class Package:
    name: str
    path: str
    repository: str


def _safe_path(value: str) -> bool:
    path = PurePosixPath(value)
    return bool(value) and not path.is_absolute() and all(
        part not in ("", ".", "..") for part in path.parts
    )


def _read_profile(name: str, profile_path: Path | None) -> list[str]:
    if not PROFILE_NAME.fullmatch(name):
        raise ResolutionError(f"invalid profile name: {name!r}")
    path = profile_path or DEPENDENCIES / "profiles" / f"{name}.packages"
    selected: list[str] = []
    seen: set[str] = set()
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        package = raw.strip()
        if not package or package.startswith("#"):
            continue
        if not PACKAGE_NAME.fullmatch(package):
            raise ResolutionError(f"invalid package in {path}:{number}: {package!r}")
        if package in seen:
            raise ResolutionError(f"duplicate package in {path}:{number}: {package}")
        seen.add(package)
        selected.append(package)
    if not selected:
        raise ResolutionError(f"empty dependency profile: {path}")
    return selected


def _read_packages(path: Path) -> dict[str, str]:
    packages: dict[str, str] = {}
    paths: set[str] = set()
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        fields = raw.split("\t")
        if len(fields) != 2 or not PACKAGE_NAME.fullmatch(fields[0]) or not _safe_path(fields[1]):
            raise ResolutionError(f"invalid package catalog record at {path}:{number}")
        name, package_path = fields
        if name in packages or package_path in paths:
            raise ResolutionError(f"duplicate package catalog record at {path}:{number}")
        packages[name] = package_path
        paths.add(package_path)
    return packages


def _read_repositories(path: Path) -> dict[str, Repository]:
    repositories: dict[str, dict[str, str]] = {}
    current: str | None = None
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#") or raw == "repositories:":
            continue
        if raw.startswith("  ") and not raw.startswith("    ") and raw.endswith(":"):
            current = raw.strip()[:-1]
            if not _safe_path(current) or current in repositories:
                raise ResolutionError(f"invalid repository at {path}:{number}")
            repositories[current] = {}
        elif raw.startswith("    ") and current and ": " in raw.strip():
            key, value = raw.strip().split(": ", 1)
            if key in repositories[current] or not value:
                raise ResolutionError(f"invalid repository field at {path}:{number}")
            repositories[current][key] = value
        else:
            raise ResolutionError(f"invalid repository catalog record at {path}:{number}")
    result: dict[str, Repository] = {}
    for repo_path, fields in repositories.items():
        if fields.get("type") != "git" or not fields.get("url") or not fields.get("version"):
            raise ResolutionError(f"incomplete repository: {repo_path}")
        result[repo_path] = Repository(repo_path, fields["url"], fields["version"])
    return result


def resolve(profile: str, profile_path: Path | None = None) -> tuple[list[Package], list[Repository]]:
    selected = _read_profile(profile, profile_path)
    catalog = _read_packages(DEPENDENCIES / "vendor-packages.tsv")
    repositories = _read_repositories(DEPENDENCIES / "autoracer.repos")
    records: list[Package] = []
    owners: set[str] = set()
    for name in selected:
        if name not in catalog:
            raise ResolutionError(f"unknown package in {profile} profile: {name}")
        package_path = catalog[name]
        candidates = [
            repo_path
            for repo_path in repositories
            if package_path == repo_path or package_path.startswith(repo_path + "/")
        ]
        if not candidates:
            raise ResolutionError(f"no repository owns package {name}: {package_path}")
        longest = max(len(candidate) for candidate in candidates)
        closest = [candidate for candidate in candidates if len(candidate) == longest]
        if len(closest) != 1:
            raise ResolutionError(f"ambiguous repository owner for package {name}")
        owner = closest[0]
        owners.add(owner)
        records.append(Package(name, package_path, owner))
    selected_repositories = [repo for path, repo in repositories.items() if path in owners]
    return records, selected_repositories


def _render(records: list[Package], repositories: list[Repository], output_format: str) -> str:
    if output_format == "names":
        return "\n".join(record.name for record in records)
    if output_format == "records":
        return "\n".join(
            f"{record.name}\t{record.path}\t{record.repository}" for record in records
        )
    if output_format == "repository-paths":
        return "\n".join(repository.path for repository in repositories)
    lines = ["repositories:"]
    for repository in repositories:
        lines.extend(
            (
                f"  {repository.path}:",
                "    type: git",
                f"    url: {repository.url}",
                f"    version: {repository.revision}",
            )
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="hooke2")
    parser.add_argument("--profile-file", type=Path)
    parser.add_argument(
        "--format", choices=("names", "records", "repository-paths", "repositories"), default="names"
    )
    args = parser.parse_args()
    try:
        records, repositories = resolve(args.profile, args.profile_file)
    except (OSError, ResolutionError) as error:
        print(f"vendor resolution failed: {error}", file=sys.stderr)
        return 2
    print(_render(records, repositories, args.format))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
