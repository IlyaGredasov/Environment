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
import os
import queue
import re
import shutil
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from tqdm import tqdm

OUTPUT_TEMPLATE = "%(playlist&{}/|)s%(title)s.%(ext)s"
DEFAULT_PROCESSES = 4
PROGRESS_MARKER = "__YT_PROGRESS__"
OUTPUT_MARKER = "__YT_OUTPUT__"
PROGRESS_PATTERN = re.compile(
    r"(?P<downloaded>\d+|NA)\|(?P<total>\d+|NA)\|"
    r"(?P<estimated_total>\d+|NA)\|(?P<vcodec>[^|]*)\|"
    r"(?P<acodec>[^|]*)\|(?P<title>.*)"
)
FFMPEG_TIME_PATTERN = re.compile(r"^(?P<hours>\d+):(?P<minutes>\d{2}):(?P<seconds>\d{2}(?:\.\d+)?)$")
ENCODER_PATTERN = re.compile(
    r"^\s*V\S*\s+(?P<name>\S+)\s+(?P<description>.+)$", re.MULTILINE
)


@dataclass(frozen=True)
class H264Encoder:
    name: str
    description: str


HARDWARE_H264_ENCODERS = (
    H264Encoder("h264_nvenc", "NVIDIA NVENC hardware acceleration"),
    H264Encoder("h264_amf", "AMD AMF hardware acceleration"),
    H264Encoder("h264_qsv", "Intel Quick Sync hardware acceleration"),
    H264Encoder("h264_d3d12va", "Direct3D 12 video acceleration"),
    H264Encoder("h264_mf", "Windows Media Foundation hardware acceleration"),
    H264Encoder("h264_videotoolbox", "Apple VideoToolbox hardware acceleration"),
    H264Encoder("h264_vaapi", "VA-API hardware acceleration"),
    H264Encoder("h264_v4l2m2m", "V4L2 M2M hardware acceleration"),
    H264Encoder("h264_vulkan", "Vulkan video acceleration"),
)
SOFTWARE_H264_ENCODERS = (
    H264Encoder("libx264", "libx264 software encoder"),
    H264Encoder("h264", "FFmpeg H.264 software encoder"),
)


def positive_process_count(value: str) -> int:
    count = int(value)
    if count < 2:
        raise argparse.ArgumentTypeError("must be at least 2")
    return count


def configure_utf8_console() -> None:
    """Keep titles readable when the script is launched from Windows PowerShell."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


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
        default=None,
        help=(
            "number of yt-dlp processes, at least 2 "
            f"(default: min({DEFAULT_PROCESSES}, number of URLs))"
        ),
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


def available_h264_encoders(ffmpeg: str) -> set[str]:
    """Get H.264 video encoder names advertised by the installed FFmpeg."""
    try:
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
        return set()
    if result.returncode:
        return set()
    return {
        match.group("name")
        for match in ENCODER_PATTERN.finditer(result.stdout)
        if "h264" in match.group("name")
        or "h.264" in match.group("description").lower()
    }


def encoder_works(ffmpeg: str, encoder: str) -> bool:
    """Check that a listed encoder can actually initialize on this computer."""
    try:
        result = subprocess.run(
            [
                ffmpeg,
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "color=c=black:s=640x360:r=1",
                "-frames:v",
                "1",
                "-an",
                "-c:v",
                encoder,
                "-f",
                "null",
                "-",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def select_h264_encoder(ffmpeg: str) -> H264Encoder:
    """Prefer the fastest functional hardware H.264 encoder, then software."""
    available = available_h264_encoders(ffmpeg)
    for encoder in (*HARDWARE_H264_ENCODERS, *SOFTWARE_H264_ENCODERS):
        if encoder.name in available and encoder_works(ffmpeg, encoder.name):
            return encoder
    raise RuntimeError("FFmpeg has no usable H.264 encoder.")


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
        "--progress",
        "--encoding",
        "utf-8",
        "--progress-template",
        (
            f"download:{PROGRESS_MARKER}%(progress.downloaded_bytes)s|"
            "%(progress.total_bytes)s|%(progress.total_bytes_estimate)s|"
            "%(info.vcodec)s|%(info.acodec)s|%(info.title)s"
        ),
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
                "--merge-output-format",
                "mkv",
                "--print",
                f"after_move:{OUTPUT_MARKER}%(filepath)s",
            )
        )
    elif mode == "mp3":
        args.extend(
            ("--extract-audio", "--audio-format", "mp3", "--audio-quality", "0")
        )

    args.append(url)
    return args


def download_stage(vcodec: str, acodec: str) -> str:
    """Name the current yt-dlp stream using its selected codecs."""
    if vcodec == "none" and acodec != "none":
        return "audio"
    return "video"


def seconds_from_ffmpeg_time(value: str) -> float | None:
    """Convert FFmpeg's HH:MM:SS.microseconds progress value to seconds."""
    match = FFMPEG_TIME_PATTERN.fullmatch(value)
    if match is None:
        return None
    return (
        int(match.group("hours")) * 3600
        + int(match.group("minutes")) * 60
        + float(match.group("seconds"))
    )


def format_clock(seconds: float | None) -> str:
    """Format a progress timestamp without tqdm's decimal-second notation."""
    if seconds is None:
        return "??:??:??"
    whole_seconds = max(0, int(seconds))
    hours, remainder = divmod(whole_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"


def format_bytes(value: int | None) -> str:
    """Render byte values in the same compact scale as tqdm's download bar."""
    return "?" if value is None else tqdm.format_sizeof(value, suffix="B", divisor=1024)


def set_stage(bar: tqdm, stage: str, title: str) -> None:
    """Put the active stage at the left and the media title beside it."""
    bar.set_description_str(stage, refresh=False)
    bar.set_postfix_str(title[:70], refresh=False)


def update_byte_bar(
    bar: tqdm,
    stage: str,
    downloaded: int,
    total: int | None,
    title: str,
) -> None:
    bar.unit = "B"
    bar.unit_scale = True
    bar.unit_divisor = 1024
    set_stage(
        bar,
        f"Downloading {stage.title()}: {format_bytes(downloaded)}/{format_bytes(total)}",
        title,
    )
    if downloaded < bar.n:
        bar.reset(total=total)
    elif total is not None:
        bar.total = total
    bar.n = downloaded
    bar.refresh()


def download(args: list[str], bar: tqdm) -> tuple[int, list[Path]]:
    output_paths: list[Path] = []
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "utf-8"
    with subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        env=environment,
    ) as process:
        assert process.stdout is not None
        for line in process.stdout:
            if OUTPUT_MARKER in line:
                output_path = line.split(OUTPUT_MARKER, 1)[1].strip()
                if output_path:
                    output_paths.append(Path(output_path))
                continue
            if PROGRESS_MARKER not in line:
                if "ERROR:" in line:
                    tqdm.write(line.rstrip(), file=sys.stderr)
                continue
            match = PROGRESS_PATTERN.search(line.split(PROGRESS_MARKER, 1)[1].strip())
            if match is None:
                continue
            downloaded_value = match.group("downloaded")
            if downloaded_value == "NA":
                continue
            downloaded = int(downloaded_value)
            total = next(
                (
                    int(value)
                    for value in (
                        match.group("total"),
                        match.group("estimated_total"),
                    )
                    if value != "NA"
                ),
                None,
            )
            title = match.group("title").strip()
            stage = download_stage(match.group("vcodec"), match.group("acodec"))
            update_byte_bar(bar, stage, downloaded, total, title)
        return process.wait(), output_paths


def media_duration(path: Path) -> float | None:
    """Read a media duration for FFmpeg's time-based progress bar."""
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        return None
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        return float(result.stdout.strip()) if result.returncode == 0 else None
    except (OSError, ValueError):
        return None


def recode_mkv(path: Path, ffmpeg: str, video_codec: str, bar: tqdm) -> None:
    """Re-encode one completed download and stream FFmpeg progress into tqdm."""
    duration = media_duration(path)
    temporary_path = path.with_name(f"{path.stem}.recode-tmp.mkv")
    output_path = path.with_suffix(".mkv")
    if temporary_path.exists():
        temporary_path.unlink()
    bar.unit = "s"
    bar.unit_scale = False
    bar.reset(total=duration)
    set_stage(bar, f"FFmpeg: {format_clock(0)}/{format_clock(duration)}", path.name)
    try:
        with subprocess.Popen(
            [
                ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(path),
                "-c:v",
                video_codec,
                "-c:a",
                "copy",
                "-progress",
                "pipe:1",
                "-nostats",
                str(temporary_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        ) as process:
            assert process.stdout is not None
            for line in process.stdout:
                key, separator, value = line.strip().partition("=")
                if separator and key in {"out_time", "out_time_us", "out_time_ms"}:
                    if key == "out_time":
                        current = seconds_from_ffmpeg_time(value)
                    else:
                        current = int(value) / 1_000_000 if value.isdigit() else None
                    if current is not None:
                        bar.n = min(current, duration) if duration is not None else current
                        set_stage(
                            bar,
                            f"FFmpeg: {format_clock(current)}/{format_clock(duration)}",
                            path.name,
                        )
                        bar.refresh()
                elif line.startswith("ERROR:"):
                    tqdm.write(line.rstrip(), file=sys.stderr)
            if process.wait() != 0:
                raise RuntimeError(f"FFmpeg failed while processing: {path}")
        os.replace(temporary_path, output_path)
        if path != output_path:
            path.unlink()
        if duration is not None:
            bar.n = duration
            set_stage(
                bar,
                f"FFmpeg: {format_clock(duration)}/{format_clock(duration)}",
                path.name,
            )
            bar.refresh()
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def main(argv: Sequence[str] | None = None) -> int:
    configure_utf8_console()
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
    video_codec = ""
    ffmpeg = ""
    if mode == "recode-mkv":
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg is None:
            print("ffmpeg was not found in PATH.", file=sys.stderr)
            return 2
        try:
            encoder = select_h264_encoder(ffmpeg)
        except RuntimeError as error:
            print(error, file=sys.stderr)
            return 2
        video_codec = encoder.name
        print(f"Selected H.264 encoder: {encoder.name} ({encoder.description}).")

    commands = [
        yt_dlp_args(url, args.output_dir, cookies, mode, video_codec) for url in urls
    ]
    failures = 0
    worker_count = min(args.processes or DEFAULT_PROCESSES, len(commands))
    print(
        f"Starting {len(commands)} yt-dlp job(s) with {worker_count} process worker(s)."
    )
    bars = [
        tqdm(
            total=None,
            desc="Preparing",
            position=i,
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
            bar_format="[{desc}] {postfix} {bar} [{elapsed}<{remaining}, {rate_fmt}]",
            leave=False,
        )
        for i in range(worker_count)
    ]
    overall_bar = tqdm(
        total=len(commands),
        desc="Tasks",
        position=worker_count,
        unit="task",
        bar_format="[{n_fmt}/{total_fmt} {desc}]",
        leave=True,
    )
    available_bars: queue.SimpleQueue[tqdm] = queue.SimpleQueue()
    for bar in bars:
        available_bars.put(bar)

    def run_download(command: list[str], job_number: int) -> int:
        bar = available_bars.get()
        bar.reset(total=None)
        set_stage(bar, "Preparing", f"job {job_number}/{len(commands)}")
        bar.refresh()
        try:
            returncode, output_paths = download(command, bar)
            if returncode == 0:
                if mode == "recode-mkv":
                    for output_path in output_paths:
                        recode_mkv(output_path, ffmpeg, video_codec, bar)
                bar.refresh()
            else:
                set_stage(bar, f"FAILED: job {job_number}/{len(commands)}", "")
            return returncode
        finally:
            available_bars.put(bar)

    try:
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=worker_count
        ) as executor:
            futures = {
                executor.submit(run_download, command, index): index
                for index, command in enumerate(commands, start=1)
            }
            for future in concurrent.futures.as_completed(futures):
                job_number = futures[future]
                try:
                    returncode = future.result()
                    if returncode:
                        failures += 1
                        tqdm.write(f"Job {job_number} failed.", file=sys.stderr)
                except Exception as error:  # noqa: BLE001
                    failures += 1
                    tqdm.write(f"Worker failed: {error}", file=sys.stderr)
                finally:
                    overall_bar.update(1)
    finally:
        for bar in bars:
            bar.close()
        overall_bar.close()

    if failures:
        print(f"{failures} yt-dlp job(s) failed.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
