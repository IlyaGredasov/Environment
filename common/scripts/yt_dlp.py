#!/usr/bin/env python3
"""Download videos listed in a file with yt-dlp in separate processes.

Each input line is handled by an independent yt-dlp invocation.  This avoids
yt-dlp's thread-safety issues while still allowing multiple URLs/playlists to
be downloaded concurrently.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

OUTPUT_TEMPLATE = "%(playlist&{}/|)s%(title)s.%(ext)s"
DEFAULT_PROCESSES = 4


def positive_process_count(value: str) -> int:
    count = int(value)
    if count < 2:
        raise argparse.ArgumentTypeError("must be at least 2")
    return count


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download yt-dlp URLs in separate OS processes.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.cwd(),
        help="directory for downloaded files (default: current directory)",
    )
    parser.add_argument(
        "--videos",
        type=Path,
        default=Path("videos.txt"),
        help="text file containing URLs, one per line (default: videos.txt)",
    )
    parser.add_argument(
        "--cookies",
        type=Path,
        default=Path("yt_cookies.txt"),
        help="Netscape cookies file (default: yt_cookies.txt; optional)",
    )
    parser.add_argument(
        "--processes",
        type=positive_process_count,
        default=DEFAULT_PROCESSES,
        help=f"number of yt-dlp processes, at least 2 (default: {DEFAULT_PROCESSES})",
    )

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--download-mkv",
        action="store_true",
        help="download/remux video into MKV without re-encoding",
    )
    mode.add_argument(
        "--recode-mkv",
        action="store_true",
        help="re-encode video as H.264 in an MKV container",
    )
    mode.add_argument(
        "--mp3",
        action="store_true",
        help="extract the best available audio as MP3",
    )
    return parser.parse_args(argv)


def read_urls(path: Path) -> list[str]:
    if not path.is_file():
        raise FileNotFoundError(f"Videos file not found: {path}")

    urls = [
        line.strip()
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not urls:
        raise ValueError(f"Videos file contains no URLs: {path}")
    return urls


def has_nvenc() -> bool:
    """Return whether the installed ffmpeg can use NVIDIA's H.264 encoder."""
    ffmpeg = shutil.which("ffmpeg")
    nvidia_smi = shutil.which("nvidia-smi")
    if ffmpeg is None or nvidia_smi is None:
        return False
    try:
        gpu = subprocess.run(
            [nvidia_smi, "-L"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        result = subprocess.run(
            [ffmpeg, "-hide_banner", "-encoders"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError:
        return False
    return (
        gpu.returncode == 0
        and bool(gpu.stdout.strip())
        and result.returncode == 0
        and "h264_nvenc" in result.stdout
    )


def yt_dlp_args(
    url: str,
    output_dir: Path,
    cookies: Path | None,
    mode: str | None,
    video_codec: str,
) -> list[str]:
    args = [
        "yt-dlp",
        "--paths",
        str(output_dir),
        "--output",
        OUTPUT_TEMPLATE,
        "--yes-playlist",
        "--no-check-certificates",
        "--js-runtime",
        "node",
        "--remote-components",
        "ejs:github",
        "--extractor-args",
        "generic:impersonate",
    ]
    if cookies is not None:
        args.extend(("--cookies", str(cookies)))

    if mode == "download-mkv":
        args.extend(("--merge-output-format", "mkv", "--remux-video", "mkv"))
    elif mode == "recode-mkv":
        args.extend(
            (
                "--recode-video",
                "mkv",
                "--postprocessor-args",
                f"VideoConvertor:-c:v {video_codec} -preset p5 -cq 23 -c:a copy",
            )
        )
    elif mode == "mp3":
        args.extend(
            ("--extract-audio", "--audio-format", "mp3", "--audio-quality", "0")
        )

    args.append(url)
    return args


def download(args: list[str]) -> int:
    return subprocess.run(args, check=False).returncode


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if shutil.which("yt-dlp") is None:
        print("yt-dlp was not found in PATH.", file=sys.stderr)
        return 2

    try:
        urls = read_urls(args.videos)
    except (FileNotFoundError, ValueError) as error:
        print(error, file=sys.stderr)
        return 2

    args.output_dir.mkdir(parents=True, exist_ok=True)
    cookies = args.cookies if args.cookies.is_file() else None
    if args.cookies != Path("yt_cookies.txt") and cookies is None:
        print(f"Cookies file not found: {args.cookies}", file=sys.stderr)
        return 2
    if cookies is None:
        print("Cookies file not found; continuing without cookies.", file=sys.stderr)

    mode = (
        "download-mkv"
        if args.download_mkv
        else "recode-mkv"
        if args.recode_mkv
        else "mp3"
        if args.mp3
        else None
    )
    video_codec = "h264_nvenc" if mode == "recode-mkv" and has_nvenc() else "h264"
    if mode == "recode-mkv":
        print(f"Re-encoding with {video_codec}.")

    commands = [
        yt_dlp_args(url, args.output_dir, cookies, mode, video_codec) for url in urls
    ]
    print(
        f"Starting {len(commands)} yt-dlp job(s) with {args.processes} process worker(s)."
    )
    failures = 0
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.processes) as executor:
        futures = [executor.submit(download, command) for command in commands]
        for future in concurrent.futures.as_completed(futures):
            try:
                failures += future.result() != 0
            except (
                Exception  # noqa: BLE001
            ) as error:  # A worker itself could not be started.
                failures += 1
                print(f"Worker failed: {error}", file=sys.stderr)

    if failures:
        print(f"{failures} yt-dlp job(s) failed.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
