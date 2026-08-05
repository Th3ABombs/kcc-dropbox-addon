import os
import re
import shutil
import subprocess
from pathlib import Path

import dropbox
from dropbox.files import WriteMode
from flask import Flask, jsonify, request

app = Flask(__name__)

OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/share/kcc-output")
WATCH_ROOT = os.environ.get("WATCH_ROOT", "/share/suwayomi/downloads/mangas")
DROPBOX_TOKEN = os.environ.get("DROPBOX_TOKEN", "")
DROPBOX_FOLDER = os.environ.get("DROPBOX_FOLDER", "/Applicazioni/Kobo Cloud Sync")
KOBO_DEVICE = os.environ.get("KOBO_DEVICE", "Kobo Libra Colour")
FORMAT = os.environ.get("FORMAT", "KEPUB")
MANGA_MODE = os.environ.get("MANGA_MODE", "true").lower() == "true"

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

    ch_match = re.search(r"(?:Ch\.?|Chapter\.?|Cap\.?)\s*([0-9]+(?:\.[0-9]+)?)", base_name, re.IGNORECASE)
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

    with local_file.open("rb") as f:
        dbx.files_upload(
            f.read(),
            remote_path,
            mode=WriteMode.overwrite,
            mute=True
        )

    return remote_path


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
    }
    return jsonify(status)


@app.route("/convert", methods=["POST"])
def convert():
    data = request.get_json(force=True)
    source_file = data.get("file_path", "").strip()

    if not source_file:
        return jsonify({"status": "error", "message": "file_path missing"}), 400

    input_path = Path(source_file)
    if not input_path.exists():
        return jsonify({"status": "error", "message": "file not found"}), 400

    try:
        input_path.relative_to(WATCH_ROOT)
    except ValueError:
        return jsonify({"status": "error", "message": "file outside watch_root"}), 400

    manga_name, chapter = extract_chapter_info(input_path)
    safe_manga = sanitize_filename(manga_name)
    safe_chapter = sanitize_filename(chapter)
    title = f"{safe_manga} {safe_chapter}"

    output_path = Path(OUTPUT_DIR)
    output_path.mkdir(parents=True, exist_ok=True)

    before_files = set(output_path.glob("*"))
    kobo_profile = get_kobo_profile(KOBO_DEVICE)

    cmd = [
        "kcc-c2e",
        "-p", kobo_profile,
        "-f", FORMAT,
        "-o", OUTPUT_DIR,
        "-t", title,
    ]

    if MANGA_MODE:
        cmd.append("-m")

    cmd.append(str(input_path))

    subprocess.run(cmd, check=True)

    after_files = set(output_path.glob("*"))
    generated = find_generated_file(before_files, after_files)

    if generated is None:
        candidates = sorted(output_path.glob(f"*{safe_chapter}*"))
        if candidates:
            generated = candidates[-1]

    if generated is None or not generated.exists():
        return jsonify({"status": "error", "message": "converted file not found"}), 500

    extension = "".join(generated.suffixes) if generated.suffixes else f".{FORMAT.lower()}"
    final_name = f"{title}{extension}"
    final_local = output_path / final_name

    if generated != final_local:
        if final_local.exists():
            final_local.unlink()
        shutil.move(str(generated), str(final_local))

    remote_path = upload_to_dropbox(final_local, final_name)

    return jsonify({
        "status": "ok",
        "input_file": str(input_path),
        "local_output": str(final_local),
        "dropbox_path": remote_path,
        "manga": manga_name,
        "chapter": chapter,
        "kobo_device": KOBO_DEVICE,
        "kobo_profile": kobo_profile,
        "format": FORMAT
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5005)
