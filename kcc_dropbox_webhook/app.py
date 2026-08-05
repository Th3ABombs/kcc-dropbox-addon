import os
import re
import shutil
import subprocess
import time
import logging
from pathlib import Path

import dropbox
from dropbox.files import WriteMode
from flask import Flask, jsonify, request

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
)

OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/share/kcc-output")
WATCH_ROOT = os.environ.get("WATCH_ROOT", "/share/suwayomi/downloads/mangas")
DROPBOX_TOKEN = os.environ.get("DROPBOX_TOKEN", "")
DROPBOX_FOLDER = os.environ.get("DROPBOX_FOLDER", "/Applicazioni/Kobo Cloud Sync")
KOBO_DEVICE = os.environ.get("KOBO_DEVICE", "Kobo Libra Colour")
FORMAT = os.environ.get("FORMAT", "KEPUB")
MANGA_MODE = os.environ.get("MANGA_MODE", "true").lower() == "true"

KCC_TIMEOUT = int(os.environ.get("KCC_TIMEOUT", "1800"))
FILE_STABLE_TIMEOUT = int(os.environ.get("FILE_STABLE_TIMEOUT", "180"))
FILE_STABLE_FOR = int(os.environ.get("FILE_STABLE_FOR", "5"))
FILE_STABLE_INTERVAL = float(os.environ.get("FILE_STABLE_INTERVAL", "1"))

KOBO_PROFILE_MAP = {
    "Kobo Mini": "KoMT",
    "Kobo Touch": "KoMT",
    "Kobo Glo": "KoG",
    "Kobo Glo HD": "KoGHD",
    "Kobo Aura": "KoA",
    "Kobo Aura HD": "KoAHD",
    "Kobo Aura H2O": "KoAH2O",
    "Kobo Aura ONE": "KoAO",
    "Kobo Nia": "KoN",
    "Kobo Clara HD": "KoC",
    "Kobo Clara 2E": "KoC",
    "Kobo Clara Colour": "KoCC",
    "Kobo Libra H2O": "KoL",
    "Kobo Libra 2": "KoL",
    "Kobo Libra Colour": "KoLC",
    "Kobo Forma": "KoF",
    "Kobo Sage": "KoS",
    "Kobo Elipsa": "KoE",
}


def get_kobo_profile(device_name: str) -> str:
    return KOBO_PROFILE_MAP.get(device_name, "KoLC")


def sanitize_filename(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|]+', "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def extract_chapter_info(file_path: Path):
    manga_name = file_path.parent.name
    base_name = file_path.stem

    ch_match = re.search(
        r"(?:Ch\.?|Chapter\.?|Cap\.?)\s*([0-9]+(?:\.[0-9]+)?)",
        base_name,
        re.IGNORECASE
    )
    if not ch_match:
        ch_match = re.search(r"([0-9]+(?:\.[0-9]+)?)$", base_name)

    chapter = ch_match.group(1) if ch_match else "unknown"
    return manga_name, chapter


def find_generated_file(before_files, after_files):
    new_files = sorted(list(after_files - before_files))
    if new_files:
        return new_files[-1]
    return None


def upload_to_dropbox(local_file: Path, remote_filename: str):
    if not DROPBOX_TOKEN:
        raise RuntimeError("Dropbox token not configured")

    dbx = dropbox.Dropbox(DROPBOX_TOKEN)
    remote_path = f"{DROPBOX_FOLDER.rstrip('/')}/{remote_filename}"

    app.logger.info("Uploading to Dropbox: %s -> %s", local_file, remote_path)

    with local_file.open("rb") as f:
        dbx.files_upload(
            f.read(),
            remote_path,
            mode=WriteMode.overwrite,
            mute=True
        )

    return remote_path


def is_probably_temporary_file(path: Path) -> bool:
    temp_suffixes = {
        ".tmp", ".part", ".partial", ".crdownload", ".download", ".!qB", ".filepart"
    }
    lower_name = path.name.lower()

    if any(lower_name.endswith(sfx) for sfx in temp_suffixes):
        return True

    if lower_name.startswith("."):
        return True

    return False


def wait_for_file_stable(path: Path, timeout: int, stable_for: int, interval: float):
    start = time.time()
    last_size = None
    stable_since = None

    app.logger.info(
        "Waiting for file to become stable: path=%s timeout=%ss stable_for=%ss interval=%ss",
        path, timeout, stable_for, interval
    )

    while time.time() - start < timeout:
        if path.exists() and path.is_file():
            try:
                size = path.stat().st_size
            except FileNotFoundError:
                size = None

            app.logger.info("File check: path=%s size=%s", path, size)

            if size and size > 0:
                if size == last_size:
                    if stable_since is None:
                        stable_since = time.time()
                    elif (time.time() - stable_since) >= stable_for:
                        app.logger.info("File is stable: path=%s size=%s", path, size)
                        return size
                else:
                    stable_since = None
                    last_size = size

        time.sleep(interval)

    raise TimeoutError(f"file not stable within {timeout}s: {path}")


def run_kcc(cmd, timeout):
    app.logger.info("Running KCC command: %s", cmd)
    return subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout
    )


@app.route("/health", methods=["GET"])
def health():
    status = {
        "status": "running",
        "output_dir": OUTPUT_DIR,
        "watch_root": WATCH_ROOT,
        "dropbox_folder": DROPBOX_FOLDER,
        "kobo_device": KOBO_DEVICE,
        "kobo_profile": get_kobo_profile(KOBO_DEVICE),
        "format": FORMAT,
        "manga_mode": MANGA_MODE,
        "dropbox_configured": bool(DROPBOX_TOKEN),
        "kcc_timeout": KCC_TIMEOUT,
        "file_stable_timeout": FILE_STABLE_TIMEOUT,
        "file_stable_for": FILE_STABLE_FOR,
        "file_stable_interval": FILE_STABLE_INTERVAL,
    }
    return jsonify(status)


@app.route("/convert", methods=["POST"])
def convert():
    try:
        data = request.get_json(force=True) or {}
    except Exception as exc:
        app.logger.exception("Invalid JSON payload")
        return jsonify({
            "status": "error",
            "message": "invalid JSON payload",
            "error": str(exc)
        }), 400

    source_file = str(data.get("file_path", "")).strip()
    app.logger.info("Received convert request: file_path=%s", source_file)

    if not source_file:
        return jsonify({
            "status": "error",
            "message": "file_path missing"
        }), 400

    input_path = Path(source_file)

    if is_probably_temporary_file(input_path):
        app.logger.warning("Temporary file ignored: %s", input_path)
        return jsonify({
            "status": "ignored",
            "message": "temporary file ignored",
            "input_file": str(input_path)
        }), 202

    if not input_path.exists():
        app.logger.warning("Input file not found: %s", input_path)
        return jsonify({
            "status": "error",
            "message": "file not found",
            "input_file": str(input_path)
        }), 400

    watch_root_path = Path(WATCH_ROOT)
    try:
        input_path.resolve().relative_to(watch_root_path.resolve())
    except ValueError:
        app.logger.warning("File outside watch_root: %s", input_path)
        return jsonify({
            "status": "error",
            "message": "file outside watch_root",
            "input_file": str(input_path),
            "watch_root": str(watch_root_path)
        }), 400

    try:
        stable_size = wait_for_file_stable(
            input_path,
            timeout=FILE_STABLE_TIMEOUT,
            stable_for=FILE_STABLE_FOR,
            interval=FILE_STABLE_INTERVAL
        )
    except Exception as exc:
        app.logger.exception("File not ready for conversion: %s", input_path)
        return jsonify({
            "status": "error",
            "message": "source file not ready",
            "error": str(exc),
            "input_file": str(input_path)
        }), 500

    manga_name, chapter = extract_chapter_info(input_path)
    safe_manga = sanitize_filename(manga_name)
    safe_chapter = sanitize_filename(chapter)
    title = f"{safe_manga} {safe_chapter}"

    output_path = Path(OUTPUT_DIR)
    output_path.mkdir(parents=True, exist_ok=True)

    before_files = set(output_path.glob("*"))
    kobo_profile = get_kobo_profile(KOBO_DEVICE)

    cmd = [
        "python3",
        "/opt/kcc/kcc-c2e.py",
        "-p", kobo_profile,
        "-f", FORMAT,
        "-o", OUTPUT_DIR,
        "-t", title,
    ]

    if MANGA_MODE:
        cmd.append("-m")

    cmd.append(str(input_path))

    try:
        result = run_kcc(cmd, timeout=KCC_TIMEOUT)
        app.logger.info("KCC stdout: %s", result.stdout.strip())
        if result.stderr.strip():
            app.logger.info("KCC stderr: %s", result.stderr.strip())
    except subprocess.TimeoutExpired as exc:
        app.logger.exception("KCC timed out")
        return jsonify({
            "status": "error",
            "message": f"kcc conversion timed out after {KCC_TIMEOUT}s",
            "stdout": exc.stdout,
            "stderr": exc.stderr,
            "command": cmd,
            "input_file": str(input_path)
        }), 500
    except subprocess.CalledProcessError as exc:
        app.logger.exception("KCC conversion failed")
        return jsonify({
            "status": "error",
            "message": "kcc conversion failed",
            "returncode": exc.returncode,
            "stdout": exc.stdout,
            "stderr": exc.stderr,
            "command": cmd,
            "input_file": str(input_path),
            "stable_size": stable_size
        }), 500
    except FileNotFoundError as exc:
        app.logger.exception("Required executable not found")
        return jsonify({
            "status": "error",
            "message": f"required executable not found: {exc.filename}",
            "command": cmd
        }), 500
    except Exception as exc:
        app.logger.exception("Unexpected error during KCC conversion")
        return jsonify({
            "status": "error",
            "message": "unexpected conversion error",
            "error": str(exc),
            "command": cmd
        }), 500

    after_files = set(output_path.glob("*"))
    generated = find_generated_file(before_files, after_files)

    if generated is None:
        candidates = sorted(output_path.glob(f"*{safe_chapter}*"))
        if candidates:
            generated = candidates[-1]

    if generated is None or not generated.exists():
        app.logger.error("Converted file not found after KCC execution")
        return jsonify({
            "status": "error",
            "message": "converted file not found",
            "output_dir": OUTPUT_DIR,
            "input_file": str(input_path)
        }), 500

    extension = "".join(generated.suffixes) if generated.suffixes else f".{FORMAT.lower()}"
    final_name = f"{title}{extension}"
    final_local = output_path / final_name

    if generated != final_local:
        if final_local.exists():
            final_local.unlink()
        shutil.move(str(generated), str(final_local))

    try:
        remote_path = upload_to_dropbox(final_local, final_name)
    except Exception as exc:
        app.logger.exception("Dropbox upload failed")
        return jsonify({
            "status": "error",
            "message": "dropbox upload failed",
            "error": str(exc),
            "local_output": str(final_local),
            "input_file": str(input_path)
        }), 500

    response = {
        "status": "ok",
        "input_file": str(input_path),
        "stable_size": stable_size,
        "local_output": str(final_local),
        "dropbox_path": remote_path,
        "manga": manga_name,
        "chapter": chapter,
        "kobo_device": KOBO_DEVICE,
        "kobo_profile": kobo_profile,
        "format": FORMAT
    }

    app.logger.info("Conversion completed successfully: %s", response)
    return jsonify(response)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5005)
