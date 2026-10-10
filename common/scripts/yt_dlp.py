#!/usr/bin/env python3
# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "tqdm>=4.70.1",
# ]
# ///
"""Download videos listed in a file with yt-dlp in separate processes.

Each input line is handled by an independent yt-dlp invocation.  This avoids
yt-dlp's thread-safety issues while still allowing multiple URLs/playlists to
be downloaded concurrently.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import re
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from tqdm import tqdm

OUTPUT_TEMPLATE = "%(playlist&{}/|)s%(title)s.%(ext)s"
DEFAULT_PROCESSES = 4
PROGRESS_MARKER = "__YT_PROGRESS__"
PROGRESS_PATTERN = re.compile(r"(\d+(?:\.\d+)?)%\|?(.*)")


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
        "--newline",
        "--progress-template",
        f"download:{PROGRESS_MARKER}%(progress._percent_str)s|%(info.title)s",
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


def download(args: list[str], bar: tqdm) -> int:
    with subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    ) as process:
        assert process.stdout is not None
        for line in process.stdout:
            if PROGRESS_MARKER not in line:
                if "ERROR:" in line:
                    tqdm.write(line.rstrip(), file=sys.stderr)
                continue
            match = PROGRESS_PATTERN.search(line.split(PROGRESS_MARKER, 1)[1].strip())
            if match is None:
                continue
            percent = min(100.0, max(0.0, float(match.group(1))))
            title = match.group(2).strip()
            if title:
                bar.set_description_str(title[:45], refresh=False)
            bar.n = percent
            bar.refresh()
        return process.wait()


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
    bars = [
        tqdm(total=100, desc=f"Video {i + 1}", position=i, unit="%", leave=True)
        for i in range(len(commands))
    ]
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.processes) as executor:
            futures = {
                executor.submit(download, command, bar): bar
                for command, bar in zip(commands, bars)
            }
            for future in concurrent.futures.as_completed(futures):
                bar = futures[future]
                try:
                    returncode = future.result()
                    if returncode:
                        failures += 1
                        bar.set_description_str(f"FAILED: {bar.desc}")
                    else:
                        bar.n = 100
                        bar.refresh()
                except Exception as error:
                    failures += 1
                    tqdm.write(f"Worker failed: {error}", file=sys.stderr)
    finally:
        for bar in bars:
            bar.close()

    if failures:
        print(f"{failures} yt-dlp job(s) failed.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
