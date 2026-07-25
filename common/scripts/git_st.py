from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def default_root() -> Path:
    if sys.platform == "win32":
        return Path("F:/Programming")
    return Path("~/Programming").expanduser()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Print git status for repositories with a non-empty git diff."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=default_root(),
        help="Directory to search (default: F:\\Programming on Windows, ~/Programming elsewhere)",
    )
    return parser.parse_args()


def find_repositories(root: Path) -> list[Path]:
    repositories: list[Path] = []
    for directory, subdirectories, _ in os.walk(root):
        subdirectories.sort(key=str.lower)
        if ".git" in subdirectories:
            repositories.append(Path(directory))
            subdirectories.remove(".git")
    return repositories


def has_diff(repository: Path) -> bool:
    result = subprocess.run(
        ("git", "diff", "--quiet"),
        cwd=repository,
        check=False,
    )
    if result.returncode in (0, 1):
        return result.returncode == 1

    print(f"Cannot check git diff: {repository}", file=sys.stderr)
    return False


def print_status(repository: Path) -> None:
    print(f"\n[{repository}]")
    subprocess.run(("git", "status"), cwd=repository, check=False)


def main() -> int:
    args = parse_args()
    root = args.root.expanduser().resolve()
    if not root.is_dir():
        print(f"Not a directory: {root}", file=sys.stderr)
        return 2

    for repository in find_repositories(root):
        if has_diff(repository):
            print_status(repository)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
