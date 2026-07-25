from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

COLORS = ("cyan", "green", "yellow", "magenta", "white")
ANSI_COLORS = {
    "cyan": "\033[36m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "magenta": "\033[35m",
    "white": "\033[37m",
}
RESET = "\033[0m"


def default_root() -> Path:
    if sys.platform == "win32":
        return Path("F:/Programming")
    return Path("~/Programming").expanduser()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run 'uv lock --upgrade' and 'uv sync --upgrade' in uv projects."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=default_root(),
        help="Directory to search (default: F:\\Programming on Windows, ~/Programming elsewhere)",
    )
    return parser.parse_args()


def find_projects(root: Path) -> list[Path]:
    projects: list[Path] = []
    for directory, subdirectories, _ in os.walk(root):
        if ".venv" in subdirectories:
            projects.append(Path(directory))
            subdirectories.remove(".venv")
    return sorted(projects, key=lambda path: str(path).lower())


def label(project: Path, root: Path) -> str:
    try:
        return str(project.relative_to(root)) or "."
    except ValueError:
        return str(project)


async def pipe_output(stream: asyncio.StreamReader, prefix: str, color: str) -> None:
    while line := await stream.readline():
        text = line.decode(errors="replace").rstrip()
        print(f"{ANSI_COLORS[color]}[{prefix}]{RESET} {text}", flush=True)


async def run_command(project: Path, prefix: str, color: str, *command: str) -> int:
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=project,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    assert process.stdout is not None
    await pipe_output(process.stdout, prefix, color)
    return await process.wait()


async def update_project(project: Path, root: Path, color: str) -> tuple[Path, bool]:
    prefix = label(project, root)
    print(f"{ANSI_COLORS[color]}Start: {project}{RESET}", flush=True)
    try:
        if await run_command(project, prefix, color, "uv", "lock", "--upgrade") != 0:
            print(f"{ANSI_COLORS[color]}Failed: {project} (uv lock){RESET}", flush=True)
            return project, False
        if await run_command(project, prefix, color, "uv", "sync", "--upgrade") != 0:
            print(f"{ANSI_COLORS[color]}Failed: {project} (uv sync){RESET}", flush=True)
            return project, False
    except FileNotFoundError:
        print("uv executable was not found in PATH.", file=sys.stderr, flush=True)
        return project, False

    print(f"{ANSI_COLORS[color]}Synced: {project}{RESET}", flush=True)
    return project, True


async def main() -> int:
    args = parse_args()
    root = args.root.expanduser().resolve()
    if not root.is_dir():
        print(f"Not a directory: {root}", file=sys.stderr)
        return 2

    projects = find_projects(root)
    if not projects:
        print(f"No .venv directories found below: {root}")
        return 0

    print(f"Found {len(projects)} project(s) below: {root}")
    results = await asyncio.gather(
        *(
            update_project(project, root, COLORS[index % len(COLORS)])
            for index, project in enumerate(projects)
        )
    )
    failed = [project for project, succeeded in results if not succeeded]
    if failed:
        print(f"Failed projects: {len(failed)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
