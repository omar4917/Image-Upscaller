import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import traceback
import zipfile

import requests

# Download URLs
RIFE_URL = "https://github.com/nihui/rife-ncnn-vulkan/releases/download/20221029/rife-ncnn-vulkan-20221029-windows.zip"
FFMPEG_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"

import sys

# Support PyInstaller frozen path
if getattr(sys, 'frozen', False):
    SCRIPT_DIR = os.path.dirname(sys.executable)
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

ENGINES_DIR = os.path.join(SCRIPT_DIR, "engines")
RIFE_DIR = os.path.join(ENGINES_DIR, "rife-ncnn-vulkan-20221029-windows")
RIFE_EXE = os.path.join(RIFE_DIR, "rife-ncnn-vulkan.exe")
FFMPEG_DIR = os.path.join(ENGINES_DIR, "ffmpeg-master-latest-win64-gpl")
FFMPEG_EXE = os.path.join(FFMPEG_DIR, "bin", "ffmpeg.exe")
FFPROBE_EXE = os.path.join(FFMPEG_DIR, "bin", "ffprobe.exe")

# Log file for diagnostics
LOG_FILE = os.path.join(SCRIPT_DIR, "rife_debug.log")


def _log(msg):
    """Append a timestamped message to the debug log."""
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass


def is_engine_installed():
    return os.path.exists(RIFE_EXE) and os.path.exists(FFMPEG_EXE)


def _format_bytes(num_bytes):
    """Format a byte count for user-facing messages."""
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(max(num_bytes, 0))
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}"
        value /= 1024


def _get_free_space_bytes(path):
    """Return free disk space for the filesystem containing path."""
    try:
        return shutil.disk_usage(os.path.abspath(path)).free
    except Exception:
        return 0


def _choose_temp_root(input_path, output_path):
    """Pick the temp location with the most free space among sensible candidates."""
    candidates = []
    seen = set()

    for raw_path in (
        tempfile.gettempdir(),
        os.path.dirname(os.path.abspath(output_path)),
        os.path.dirname(os.path.abspath(input_path)),
        SCRIPT_DIR,
    ):
        if not raw_path:
            continue
        path = os.path.abspath(raw_path)
        key = os.path.normcase(path)
        if key in seen:
            continue
        seen.add(key)
        candidates.append((path, _get_free_space_bytes(path)))

    if not candidates:
        fallback = os.path.join(SCRIPT_DIR, "temp")
        os.makedirs(fallback, exist_ok=True)
        return fallback

    best_path, _ = max(candidates, key=lambda item: item[1])
    temp_root = os.path.join(best_path, "ai_video_interpolator_temp")
    os.makedirs(temp_root, exist_ok=True)
    return temp_root


def _estimate_average_file_size(directory, limit=120):
    """Estimate average file size from a sample of files in a directory."""
    total_bytes = 0
    file_count = 0

    try:
        for entry in os.scandir(directory):
            if not entry.is_file():
                continue
            total_bytes += entry.stat().st_size
            file_count += 1
            if file_count >= limit:
                break
    except Exception:
        return 0

    if file_count == 0:
        return 0

    return total_bytes / file_count


def _build_stall_guidance(multiplier, use_gpu):
    """Build context-aware recovery guidance for a generic RIFE stall."""
    suggestions = []

    if multiplier > 2:
        suggestions.append(f"Use 2x instead of {multiplier}x")
    else:
        suggestions.append("Try a different model such as rife-v4.6 or rife-anime")

    if use_gpu:
        suggestions.append("Turn off GPU and retry in CPU mode")
    else:
        suggestions.append("Close other CPU-heavy apps and retry")

    suggestions.append("Make sure the temp drive has plenty of free space")

    return ", ".join(f"{index}) {item}" for index, item in enumerate(suggestions, start=1))


def _build_disk_write_error(temp_root, free_space, output_sample_path):
    """Build a clear error for output-frame write failures."""
    return (
        "RIFE could not write more output frames to disk. "
        f"Temp folder: {temp_root}. "
        f"Free space left there: {_format_bytes(free_space)}. "
        "This usually means the temp drive is full or blocked from writing. "
        f"Example failed frame: {output_sample_path}. "
        "Try moving temporary files to a drive with more free space or free up disk space and retry."
    )


def _remove_dir(path):
    """Robustly removes a directory, retrying on Windows lock errors."""
    if not os.path.exists(path):
        return
    for _ in range(5):
        try:
            shutil.rmtree(path)
            return
        except OSError:
            time.sleep(0.5)


def _clean_dir(path):
    """Robustly cleans a directory and ensures it exists."""
    _remove_dir(path)
    os.makedirs(path, exist_ok=True)


def _download_and_extract(url, extract_to, progress_callback, label_prefix):
    zip_path = os.path.join(ENGINES_DIR, "temp.zip")

    response = requests.get(url, stream=True)
    total_length = response.headers.get("content-length")

    if total_length is None:
        with open(zip_path, "wb") as f:
            f.write(response.content)
    else:
        downloaded = 0
        total_length = int(total_length)
        with open(zip_path, "wb") as f:
            for data in response.iter_content(chunk_size=4096):
                downloaded += len(data)
                f.write(data)
                if progress_callback:
                    progress_callback(f"{label_prefix}: {int((downloaded / total_length) * 100)}%")

    if progress_callback:
        progress_callback(f"{label_prefix}: Extracting...")

    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(extract_to)

    os.remove(zip_path)


def download_engine(progress_callback=None):
    if not os.path.exists(ENGINES_DIR):
        os.makedirs(ENGINES_DIR)

    if not os.path.exists(RIFE_EXE):
        _download_and_extract(RIFE_URL, ENGINES_DIR, progress_callback, "Downloading RIFE AI")

    if not os.path.exists(FFMPEG_EXE):
        _download_and_extract(FFMPEG_URL, ENGINES_DIR, progress_callback, "Downloading FFmpeg")


def get_video_fps(video_path):
    cmd = [
        FFPROBE_EXE,
        "-v", "0",
        "-of", "csv=p=0",
        "-select_streams", "v:0",
        "-show_entries", "stream=r_frame_rate",
        video_path,
    ]
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        startupinfo=startupinfo,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    rate_str = result.stdout.strip()
    if not rate_str:
        raise Exception(f"Could not detect video FPS. ffprobe stderr: {result.stderr[:200]}")
    rate_str = rate_str.split("\n")[0].strip()
    if "/" in rate_str:
        num, den = rate_str.split("/")
        return float(num) / float(den)
    return float(rate_str)


def get_video_resolution(video_path):
    """Get video width and height."""
    cmd = [
        FFPROBE_EXE,
        "-v", "0",
        "-of", "csv=p=0",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        video_path,
    ]
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        startupinfo=startupinfo,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    parts = result.stdout.strip().split(",")
    if len(parts) >= 2:
        return int(parts[0]), int(parts[1])
    return None, None


def _count_files(directory):
    """Count files in a directory safely."""
    try:
        return len(os.listdir(directory))
    except Exception:
        return 0


def interpolate_video(input_path, output_path, multiplier=2, model="rife-v4.6",
                      use_gpu=True, progress_callback=None, completion_callback=None,
                      error_callback=None):
    if not is_engine_installed():
        if error_callback:
            error_callback("Engines not installed")
        return

    def run():
        temp_root = _choose_temp_root(input_path, output_path)
        temp_job_dir = tempfile.mkdtemp(prefix="rife_job_", dir=temp_root)
        temp_input_frames = os.path.join(temp_job_dir, "input_frames")
        temp_output_frames = os.path.join(temp_job_dir, "output_frames")
        rife_log_path = os.path.join(SCRIPT_DIR, "rife_output.log")

        try:
            _log(f"=== Starting interpolation: {input_path} ===")
            _log(f"Multiplier: {multiplier}, Model: {model}, GPU: {use_gpu}")
            _log(f"Temp root: {temp_root}")
            _log(f"Temp job dir: {temp_job_dir}")

            _clean_dir(temp_input_frames)
            _clean_dir(temp_output_frames)

            orig_fps = get_video_fps(input_path)
            target_fps = orig_fps * multiplier
            _log(f"Original FPS: {orig_fps}, Target FPS: {target_fps}")

            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

            if progress_callback:
                progress_callback("Step 1/3: Extracting Frames...")

            cmd_extract = [
                FFMPEG_EXE, "-i", input_path,
                "-q:v", "2",
                "-vsync", "0",
                os.path.join(temp_input_frames, "frame_%08d.png"),
            ]
            _log(f"FFmpeg extract cmd: {' '.join(cmd_extract)}")
            result = subprocess.run(
                cmd_extract,
                capture_output=True,
                text=True,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if result.returncode != 0:
                _log(f"FFmpeg extract FAILED: {result.stderr[:500]}")
                raise Exception(f"FFmpeg frame extraction failed: {result.stderr[:300]}")

            num_frames = len([f for f in os.listdir(temp_input_frames) if f.endswith(".png")])
            if num_frames == 0:
                raise Exception("No frames were extracted from the video")

            target_frame_count = num_frames * multiplier

            _log(f"Extracted {num_frames} frames")
            if progress_callback:
                progress_callback(f"Step 1/3: Extracted {num_frames} frames")

            average_input_frame_size = _estimate_average_file_size(temp_input_frames)
            estimated_output_bytes = int(average_input_frame_size * target_frame_count)
            free_space_after_extract = _get_free_space_bytes(temp_job_dir)
            safety_margin_bytes = max(2 * 1024 ** 3, estimated_output_bytes // 10)
            required_free_bytes = estimated_output_bytes + safety_margin_bytes

            _log(
                "Estimated output space: "
                f"{_format_bytes(estimated_output_bytes)}, free after extract: "
                f"{_format_bytes(free_space_after_extract)}"
            )

            if estimated_output_bytes > 0 and free_space_after_extract < required_free_bytes:
                raise Exception(
                    "Not enough free space for interpolated frames. "
                    f"Temp folder: {temp_root}. "
                    f"Estimated additional space needed: {_format_bytes(required_free_bytes)}. "
                    f"Free space available there: {_format_bytes(free_space_after_extract)}. "
                    "Free up space or use a drive with more room and retry."
                )

            model_path = os.path.join(RIFE_DIR, model)
            cmd_rife = [
                RIFE_EXE,
                "-i", temp_input_frames,
                "-o", temp_output_frames,
                "-n", str(target_frame_count),
                "-m", model_path,
                "-f", "%08d.png",
                "-j", "1:2:2",
            ]

            if not use_gpu:
                cmd_rife.extend(["-g", "-1"])

            _log(f"RIFE cmd: {' '.join(cmd_rife)}")

            if progress_callback:
                progress_callback(
                    f"Step 2/3: AI Interpolation ({num_frames} -> {target_frame_count} frames)..."
                )

            with open(rife_log_path, "w", encoding="utf-8") as rife_log_file:
                process = subprocess.Popen(
                    cmd_rife,
                    stdout=rife_log_file,
                    stderr=rife_log_file,
                    startupinfo=startupinfo,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )

            stall_timeout = 300
            last_count = 0
            last_change_time = time.time()
            was_killed = False
            last_known_free_space = _get_free_space_bytes(temp_job_dir)

            while process.poll() is None:
                time.sleep(1.5)

                current_count = _count_files(temp_output_frames)
                last_known_free_space = _get_free_space_bytes(temp_job_dir)

                if current_count != last_count:
                    last_count = current_count
                    last_change_time = time.time()

                if target_frame_count > 0 and progress_callback:
                    pct = min((current_count / target_frame_count) * 100, 99.9)
                    stall_secs = time.time() - last_change_time
                    if stall_secs > 60:
                        progress_callback(
                            f"Step 2/3: AI Interpolation ({pct:.1f}%) "
                            f"- no new frames for {int(stall_secs)}s"
                        )
                    else:
                        progress_callback(f"Step 2/3: AI Interpolation ({pct:.1f}%)")

                if time.time() - last_change_time > stall_timeout:
                    _log(f"RIFE stalled at {last_count}/{target_frame_count} - killing")
                    was_killed = True
                    process.kill()
                    process.wait()
                    break

            if not was_killed:
                process.wait()

            rife_output = ""
            try:
                with open(rife_log_path, "r", encoding="utf-8", errors="replace") as f:
                    rife_output = f.read()
                _log(f"RIFE output:\n{rife_output[-1000:]}")
            except Exception:
                pass

            has_encode_failures = "encode image" in rife_output.lower()
            failed_output_match = re.search(
                r"encode image ([^\r\n]+) failed",
                rife_output,
                flags=re.IGNORECASE,
            )
            failed_output_path = failed_output_match.group(1) if failed_output_match else temp_output_frames

            if was_killed:
                if has_encode_failures:
                    raise Exception(
                        _build_disk_write_error(
                            temp_root,
                            last_known_free_space,
                            failed_output_path,
                        )
                    )

                raise Exception(
                    f"RIFE stalled at {last_count}/{target_frame_count} frames "
                    f"with no progress for {stall_timeout}s. "
                    f"Try: {_build_stall_guidance(multiplier, use_gpu)}."
                )

            if process.returncode != 0:
                error_code = process.returncode
                if has_encode_failures:
                    raise Exception(
                        _build_disk_write_error(
                            temp_root,
                            last_known_free_space,
                            failed_output_path,
                        )
                    )

                if error_code in (4294967295, -1):
                    raise Exception(
                        f"RIFE GPU/Vulkan crash (code {error_code}). "
                        "Try: 1) Turn off 'Use GPU' to run in CPU mode, "
                        "2) Update your GPU drivers, "
                        f"3) Close other apps using the GPU.\nRIFE log: {rife_output[-300:]}"
                    )

                raise Exception(
                    f"RIFE failed (code {error_code}).\n"
                    f"RIFE log: {rife_output[-300:]}"
                )

            output_frame_count = _count_files(temp_output_frames)
            _log(f"RIFE produced {output_frame_count} output frames (expected ~{target_frame_count})")

            if output_frame_count == 0:
                raise Exception(
                    "RIFE finished but produced 0 output frames. "
                    f"Check rife_output.log for details.\nRIFE log: {rife_output[-300:]}"
                )

            if progress_callback:
                progress_callback("Step 3/3: Reconstructing Video & Audio...")

            cmd_merge = [
                FFMPEG_EXE, "-framerate", str(target_fps),
                "-i", os.path.join(temp_output_frames, "%08d.png"),
                "-i", input_path,
                "-map", "0:v", "-map", "1:a?",
                "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
                "-c:a", "copy", "-shortest", "-y", output_path,
            ]
            _log(f"FFmpeg merge cmd: {' '.join(cmd_merge)}")
            result = subprocess.run(
                cmd_merge,
                capture_output=True,
                text=True,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if result.returncode != 0:
                _log(f"FFmpeg merge FAILED: {result.stderr[:500]}")
                raise Exception(f"FFmpeg video reconstruction failed: {result.stderr[:300]}")

            if progress_callback:
                progress_callback("Cleaning up temporary files...")
            _remove_dir(temp_job_dir)

            _log(f"=== Completed successfully: {output_path} ===")
            if completion_callback:
                completion_callback()

        except Exception as e:
            _log(f"ERROR: {e}\n{traceback.format_exc()}")
            _remove_dir(temp_job_dir)
            if error_callback:
                error_callback(str(e))

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
