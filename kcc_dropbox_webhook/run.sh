#!/bin/sh
set -eu

OPTIONS_FILE="/data/options.json"

OUTPUT_DIR="$(jq -r '.output_dir // "/share/kcc-output"' "${OPTIONS_FILE}")"
WATCH_ROOT="$(jq -r '.watch_root // "/share/suwayomi/downloads/mangas"' "${OPTIONS_FILE}")"
DROPBOX_TOKEN="$(jq -r '.dropbox_token // ""' "${OPTIONS_FILE}")"
DROPBOX_FOLDER="$(jq -r '.dropbox_folder // "/Applicazioni/Kobo Cloud Sync"' "${OPTIONS_FILE}")"
PROFILE="$(jq -r '.profile // "KA"' "${OPTIONS_FILE}")"
FORMAT="$(jq -r '.format // "EPUB"' "${OPTIONS_FILE}")"
MANGA_MODE="$(jq -r '.manga_mode // true' "${OPTIONS_FILE}")"

mkdir -p "${OUTPUT_DIR}"

export OUTPUT_DIR
export WATCH_ROOT
export DROPBOX_TOKEN
export DROPBOX_FOLDER
export PROFILE
export FORMAT
export MANGA_MODE

exec python3 /app.py
