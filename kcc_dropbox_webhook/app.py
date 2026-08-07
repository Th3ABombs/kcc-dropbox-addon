import os
import re
import shutil
import subprocess
import time
import logging
import threading
import queue
import uuid
from pathlib import Path
from typing import Optional

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
DROPBOX_FOLDER = os.environ.get("DROPBOX_FOLDER", "/Applicazioni/Kobo Cloud Sync")
DROPBOX_APP_KEY = os.environ.get("DROPBOX_APP_KEY", "")
DROPBOX_APP_SECRET = os.environ.get("DROPBOX_APP_SECRET", "")
DROPBOX_REFRESH_TOKEN = os.environ.get("DROPBOX_REFRESH_TOKEN", "")
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

task_queue = queue.Queue()
jobs = {}
jobs_lock = threading.Lock()


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


def get_dropbox_client():
    if not DROPBOX_APP_KEY or not DROPBOX_APP_SECRET or not DROPBOX_REFRESH_TOKEN:
        raise RuntimeError("Dropbox app key, app secret, or refresh token not configured")

    return dropbox.Dropbox(
        app_key=DROPBOX_APP_KEY,
        app_secret=DROPBOX_APP_SECRET,
        oauth2_refresh_token=DROPBOX_REFRESH_TOKEN
    )


def upload_to_dropbox(local_file: Path, remote_filename: str):
    dbx = get_dropbox_client()
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


def utc_now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def serialize_job(job):
    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "file_path": job["file_path"],
        "created_at": job["created_at"],
        "started_at": job.get("started_at"),
        "finished_at": job.get("finished_at"),
        "result": job.get("result"),
        "error": job.get("error"),
    }


def count_jobs_by_status():
    with jobs_lock:
        counts = {
            "queued": 0,
            "processing": 0,
            "done": 0,
            "error": 0,
        }
        for job in jobs.values():
            status = job["status"]
            counts[status] = counts.get(status, 0) + 1
        return counts


def find_existing_job_for_file(file_path: str) -> Optional[dict]:
    with jobs_lock:
        for job in jobs.values():
            if job["file_path"] == file_path and job["status"] in ("queued", "processing"):
                return serialize_job(job)
    return None


def set_job_status(job_id, status, **extra):
    with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            return
        job["status"] = status
        job.update(extra)


def process_file(input_path: Path):
    watch_root_path = Path(WATCH_ROOT)
    try:
        input_path.resolve().relative_to(watch_root_path.resolve())
    except ValueError:
        raise RuntimeError(f"file outside watch_root: {input_path}")

    stable_size = wait_for_file_stable(
        input_path,
        timeout=FILE_STABLE_TIMEOUT,
        stable_for=FILE_STABLE_FOR,
        interval=FILE_STABLE_INTERVAL
    )

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

    result = run_kcc(cmd, timeout=KCC_TIMEOUT)
    app.logger.info("KCC stdout: %s", result.stdout.strip())
    if result.stderr.strip():
        app.logger.info("KCC stderr: %s", result.stderr.strip())

    after_files = set(output_path.glob("*"))
    generated = find_generated_file(before_files, after_files)

    if generated is None:
        candidates = sorted(output_path.glob(f"*{safe_chapter}*"))
        if candidates:
            generated = candidates[-1]

    if generated is None or not generated.exists():
        raise RuntimeError("converted file not found")

    extension = "".join(generated.suffixes) if generated.suffixes else f".{FORMAT.lower()}"
    final_name = f"{title}{extension}"
    final_local = output_path / final_name

    if generated != final_local:
        if final_local.exists():
            final_local.unlink()
        shutil.move(str(generated), str(final_local))

    remote_path = upload_to_dropbox(final_local, final_name)

    return {
        "input_file": str(input_path),
        "stable_size": stable_size,
        "local_output": str(final_local),
        "dropbox_path": remote_path,
        "manga": manga_name,
        "chapter": chapter,
        "kobo_device": KOBO_DEVICE,
        "kobo_profile": kobo_profile,
        "format": FORMAT,
    }


def worker():
    app.logger.info("Background worker started")
    while True:
        job_id = task_queue.get()
        try:
            with jobs_lock:
                job = jobs.get(job_id)

            if not job:
                app.logger.warning("Job not found in registry: %s", job_id)
                continue

            input_path = Path(job["file_path"])
            set_job_status(job_id, "processing", started_at=utc_now(), error=None)

            app.logger.info("Processing job %s for %s", job_id, input_path)
            result = process_file(input_path)

            set_job_status(
                job_id,
                "done",
                finished_at=utc_now(),
                result=result,
                error=None
            )
            app.logger.info("Job %s completed", job_id)

        except subprocess.TimeoutExpired as exc:
            app.logger.exception("KCC timed out for job %s", job_id)
            set_job_status(
                job_id,
                "error",
                finished_at=utc_now(),
                error={
                    "message": f"kcc conversion timed out after {KCC_TIMEOUT}s",
                    "stdout": exc.stdout,
                    "stderr": exc.stderr,
                }
            )
        except subprocess.CalledProcessError as exc:
            app.logger.exception("KCC failed for job %s", job_id)
            set_job_status(
                job_id,
                "error",
                finished_at=utc_now(),
                error={
                    "message": "kcc conversion failed",
                    "returncode": exc.returncode,
                    "stdout": exc.stdout,
                    "stderr": exc.stderr,
                }
            )
        except FileNotFoundError as exc:
            app.logger.exception("Executable not found for job %s", job_id)
            set_job_status(
                job_id,
                "error",
                finished_at=utc_now(),
                error={
                    "message": f"required executable not found: {exc.filename}",
                }
            )
        except Exception as exc:
            app.logger.exception("Unexpected worker error for job %s", job_id)
            set_job_status(
                job_id,
                "error",
                finished_at=utc_now(),
                error={
                    "message": str(exc),
                }
            )
        finally:
            task_queue.task_done()


worker_thread = threading.Thread(target=worker, daemon=True)
worker_thread.start()


@app.route("/health", methods=["GET"])
def health():
    queue_counts = count_jobs_by_status()
    status = {
        "status": "running",
        "output_dir": OUTPUT_DIR,
        "watch_root": WATCH_ROOT,
        "dropbox_folder": DROPBOX_FOLDER,
        "dropbox_app_key_configured": bool(DROPBOX_APP_KEY),
        "dropbox_app_secret_configured": bool(DROPBOX_APP_SECRET),
        "dropbox_refresh_token_configured": bool(DROPBOX_REFRESH_TOKEN),
        "kobo_device": KOBO_DEVICE,
        "kobo_profile": get_kobo_profile(KOBO_DEVICE),
        "format": FORMAT,
        "manga_mode": MANGA_MODE,
        "kcc_timeout": KCC_TIMEOUT,
        "file_stable_timeout": FILE_STABLE_TIMEOUT,
        "file_stable_for": FILE_STABLE_FOR,
        "file_stable_interval": FILE_STABLE_INTERVAL,
        "queue_size": task_queue.qsize(),
        "jobs": queue_counts,
        "worker_alive": worker_thread.is_alive(),
    }
    return jsonify(status)


@app.route("/queue", methods=["GET"])
def queue_status():
    with jobs_lock:
        queued_jobs = [serialize_job(job) for job in jobs.values() if job["status"] == "queued"]
        processing_jobs = [serialize_job(job) for job in jobs.values() if job["status"] == "processing"]

    return jsonify({
        "queue_size": task_queue.qsize(),
        "queued_jobs": queued_jobs,
        "processing_jobs": processing_jobs,
        "worker_alive": worker_thread.is_alive(),
    })


@app.route("/jobs/<job_id>", methods=["GET"])
def get_job(job_id):
    with jobs_lock:
        job = jobs.get(job_id)

    if not job:
        return jsonify({
            "status": "error",
            "message": "job not found",
            "job_id": job_id
        }), 404

    return jsonify(serialize_job(job))


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

    existing_job = find_existing_job_for_file(str(input_path))
    if existing_job:
        return jsonify({
            "status": "already_queued",
            "message": "file already queued or processing",
            "job": existing_job,
            "queue_size": task_queue.qsize(),
        }), 202

    job_id = str(uuid.uuid4())
    job = {
        "job_id": job_id,
        "status": "queued",
        "file_path": str(input_path),
        "created_at": utc_now(),
        "started_at": None,
        "finished_at": None,
        "result": None,
        "error": None,
    }

    with jobs_lock:
        jobs[job_id] = job

    task_queue.put(job_id)

    return jsonify({
        "status": "queued",
        "message": "job queued successfully",
        "job_id": job_id,
        "file_path": str(input_path),
        "queue_size": task_queue.qsize(),
        "job": serialize_job(job),
    }), 202


@app.route("/jobs", methods=["GET"])
def list_jobs():
    with jobs_lock:
        all_jobs = [serialize_job(job) for job in jobs.values()]

    all_jobs.sort(key=lambda j: j["created_at"], reverse=True)

    return jsonify({
        "count": len(all_jobs),
        "jobs": all_jobs
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5005, threaded=True)
