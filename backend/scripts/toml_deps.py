"""Rewrite repeated Poetry git+subdirectory dependencies into local path dependencies.

This helper is designed for Docker/CI builds where cloning the same monorepo multiple
times can fail or slow down dependency resolution. It:
1. Finds repeated git+subdirectory dependencies in a pyproject file.
2. Clones each repeated source repo once (optionally with GitHub token auth).
3. Exports each required ref to a local folder under the provided export root.
4. Rewrites both the root pyproject and exported nested pyprojects to use path deps.

Usage:
    python scripts/toml_deps.py <pyproject_path> <export_root>
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


@dataclass
class DepTarget:
    section: str
    name: str
    git_url: str
    subdirectory: str
    ref: str


def short_sha1(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]


def normalize_git_url(url: str) -> str:
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    path = parsed.path.rstrip("/")
    path = path.removesuffix(".git")
    return f"{parsed.scheme}://{host}{path}".lower()


def parse_dep_target(section: str, name: str, spec: object) -> DepTarget | None:
    if not isinstance(spec, dict):
        return None

    git_url = spec.get("git")
    subdirectory = spec.get("subdirectory")
    if not isinstance(git_url, str) or not isinstance(subdirectory, str):
        return None

    ref = spec.get("rev") or spec.get("tag") or spec.get("branch") or "HEAD"
    return DepTarget(
        section=section,
        name=name,
        git_url=git_url,
        subdirectory=subdirectory,
        ref=str(ref),
    )


def iter_poetry_dependency_sections(
    poetry_data: dict[str, object],
) -> list[tuple[str, dict[str, object]]]:
    sections: list[tuple[str, dict[str, object]]] = []

    main_deps = poetry_data.get("dependencies", {})
    if isinstance(main_deps, dict):
        sections.append(("tool.poetry.dependencies", main_deps))

    groups = poetry_data.get("group", {})
    if isinstance(groups, dict):
        for group_name, group_data in groups.items():
            if not isinstance(group_data, dict):
                continue
            group_deps = group_data.get("dependencies", {})
            if not isinstance(group_deps, dict):
                continue
            sections.append((f"tool.poetry.group.{group_name}.dependencies", group_deps))

    return sections


def collect_git_targets(pyproject_path: Path) -> list[DepTarget]:
    data = tomllib.loads(pyproject_path.read_text())
    poetry_data = data.get("tool", {}).get("poetry", {})
    if not isinstance(poetry_data, dict):
        return []

    targets: list[DepTarget] = []
    for section, deps in iter_poetry_dependency_sections(poetry_data):
        for name, spec in deps.items():
            target = parse_dep_target(section, name, spec)
            if target is not None:
                targets.append(target)

    return targets


def load_targets(pyproject_path: Path) -> list[DepTarget]:
    targets = collect_git_targets(pyproject_path)

    by_repo: dict[str, list[DepTarget]] = {}
    for target in targets:
        by_repo.setdefault(normalize_git_url(target.git_url), []).append(target)

    repeated: list[DepTarget] = []
    for repo_targets in by_repo.values():
        if len(repo_targets) > 1:
            repeated.extend(repo_targets)

    return repeated


def load_all_git_targets(pyproject_path: Path) -> list[DepTarget]:
    return collect_git_targets(pyproject_path)


def repo_dir(repo_root: Path, normalized_url: str) -> Path:
    digest = short_sha1(normalized_url)
    return repo_root / digest


def with_github_token(url: str, token: str | None) -> str:
    if not token:
        return url

    parsed = urlsplit(url)
    if parsed.scheme != "https" or (parsed.hostname or "").lower() != "github.com":
        return url

    return urlunsplit(
        (
            parsed.scheme,
            f"x-access-token:{token}@github.com",
            parsed.path,
            parsed.query,
            parsed.fragment,
        )
    )


def ensure_repo_checkout(url: str, normalized_url: str, repo_root: Path, token: str | None) -> Path:
    checkout_dir = repo_dir(repo_root, normalized_url)
    if checkout_dir.exists():
        return checkout_dir

    checkout_dir.parent.mkdir(parents=True, exist_ok=True)
    clone_url = with_github_token(url, token)
    subprocess.run(["git", "clone", clone_url, str(checkout_dir)], check=True)
    return checkout_dir


def export_ref(repo_path: Path, export_dir: Path, ref: str) -> None:
    if export_dir.exists():
        shutil.rmtree(export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)

    git_proc = subprocess.Popen(
        ["git", "-C", str(repo_path), "archive", ref],
        stdout=subprocess.PIPE,
    )
    tar_proc = subprocess.Popen(
        ["tar", "-x", "-C", str(export_dir)],
        stdin=git_proc.stdout,
    )
    if git_proc.stdout is not None:
        git_proc.stdout.close()

    tar_code = tar_proc.wait()
    git_code = git_proc.wait()
    if git_code != 0 or tar_code != 0:
        raise RuntimeError(f"Failed to export ref '{ref}' from {repo_path}")


def rewrite_pyproject(pyproject_path: Path, replacements: dict[tuple[str, str], Path]) -> None:
    output: list[str] = []
    current_section = ""
    pyproject_dir = pyproject_path.parent

    for line in pyproject_path.read_text().splitlines(keepends=True):
        section_match = re.match(r"^\[(.+)\]\s*$", line)
        if section_match:
            current_section = section_match.group(1)
            output.append(line)
            continue

        dep_match = re.match(r"^([A-Za-z0-9_.-]+)\s*=\s*\{.*\}\s*$", line)
        if dep_match:
            dep_name = dep_match.group(1)
            key = (current_section, dep_name)
            if key in replacements:
                replacement_path = os.path.relpath(replacements[key], pyproject_dir)
                output.append(f'{dep_name} = {{ path = "{Path(replacement_path).as_posix()}" }}\n')
                continue

        output.append(line)

    pyproject_path.write_text("".join(output))


def rewrite_exported_pyprojects(
    export_root: Path,
    path_by_target: dict[tuple[str, str, str], Path],
) -> None:
    repos_root = export_root / "_repos"
    for nested_pyproject in export_root.glob("**/pyproject.toml"):
        if repos_root in nested_pyproject.parents:
            continue
        replacements: dict[tuple[str, str], Path] = {}
        nested_targets = load_all_git_targets(nested_pyproject)
        for target in nested_targets:
            key = (
                normalize_git_url(target.git_url),
                target.subdirectory,
                target.ref,
            )
            replacement_path = path_by_target.get(key)
            if replacement_path:
                replacements[(target.section, target.name)] = replacement_path

        if replacements:
            rewrite_pyproject(nested_pyproject, replacements)


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: toml_deps.py <pyproject> <export_root>", file=sys.stderr)
        return 1

    pyproject_path = Path(sys.argv[1]).resolve()
    export_root = Path(sys.argv[2]).resolve()
    repo_root = export_root / "_repos"
    token = os.getenv("CONTAINER_GITHUB_PAT") or os.getenv("GITHUB_PAT")

    targets = load_targets(pyproject_path)
    if not targets:
        print("No repeated git+subdirectory dependencies found. Skipping rewrite.")
        return 0

    export_root.mkdir(parents=True, exist_ok=True)

    replacements: dict[tuple[str, str], Path] = {}
    exported_once: set[tuple[str, str]] = set()
    path_by_target: dict[tuple[str, str, str], Path] = {}

    for target in targets:
        normalized = normalize_git_url(target.git_url)
        repo_path = ensure_repo_checkout(target.git_url, normalized, repo_root, token)

        ref_key = (normalized, target.ref)
        ref_digest = short_sha1(f"{normalized}@{target.ref}")
        ref_export_dir = export_root / ref_digest
        if ref_key not in exported_once:
            export_ref(repo_path, ref_export_dir, target.ref)
            exported_once.add(ref_key)

        dep_path = ref_export_dir / target.subdirectory
        replacements[(target.section, target.name)] = dep_path
        path_by_target[(normalized, target.subdirectory, target.ref)] = dep_path

    rewrite_pyproject(pyproject_path, replacements)
    rewrite_exported_pyprojects(export_root, path_by_target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
