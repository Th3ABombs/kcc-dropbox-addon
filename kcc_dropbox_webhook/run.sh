#!/bin/sh
set -eu

OPTIONS_FILE="/data/options.json"

OUTPUT_DIR="/share/kcc-output"
WATCH_ROOT="/share/suwayomi/downloads/mangas"
DROPBOX_FOLDER="/Applicazioni/Kobo Cloud Sync"
DROPBOX_APP_KEY=""
DROPBOX_APP_SECRET=""
DROPBOX_REFRESH_TOKEN=""
KOBO_DEVICE="Kobo Libra Colour"
FORMAT="KEPUB"
MANGA_MODE="true"
FILE_STABLE_TIMEOUT="180"
FILE_STABLE_FOR="5"
FILE_STABLE_INTERVAL="1"
KCC_TIMEOUT="1800"

if [ -f "${OPTIONS_FILE}" ] && command -v jq >/dev/null 2>&1; then
  OUTPUT_DIR="$(jq -r '.output_dir // "/share/kcc-output"' "${OPTIONS_FILE}")"
  WATCH_ROOT="$(jq -r '.watch_root // "/share/suwayomi/downloads/mangas"' "${OPTIONS_FILE}")"
  DROPBOX_FOLDER="$(jq -r '.dropbox_folder // "/Applicazioni/Kobo Cloud Sync"' "${OPTIONS_FILE}")"
  DROPBOX_APP_KEY="$(jq -r '.dropbox_app_key // ""' "${OPTIONS_FILE}")"
  DROPBOX_APP_SECRET="$(jq -r '.dropbox_app_secret // ""' "${OPTIONS_FILE}")"
  DROPBOX_REFRESH_TOKEN="$(jq -r '.dropbox_refresh_token // ""' "${OPTIONS_FILE}")"
  KOBO_DEVICE="$(jq -r '.kobo_device // "Kobo Libra Colour"' "${OPTIONS_FILE}")"
  FORMAT="$(jq -r '.format // "KEPUB"' "${OPTIONS_FILE}")"
  MANGA_MODE="$(jq -r '.manga_mode // true' "${OPTIONS_FILE}")"
  FILE_STABLE_TIMEOUT="$(jq -r '.file_stable_timeout // 180' "${OPTIONS_FILE}")"
  FILE_STABLE_FOR="$(jq -r '.file_stable_for // 5' "${OPTIONS_FILE}")"
  FILE_STABLE_INTERVAL="$(jq -r '.file_stable_interval // 1' "${OPTIONS_FILE}")"
  KCC_TIMEOUT="$(jq -r '.kcc_timeout // 1800' "${OPTIONS_FILE}")"
fi

export OUTPUT_DIR
export WATCH_ROOT
export DROPBOX_FOLDER
export DROPBOX_APP_KEY
export DROPBOX_APP_SECRET
export DROPBOX_REFRESH_TOKEN
export KOBO_DEVICE
export FORMAT
export MANGA_MODE
export FILE_STABLE_TIMEOUT
export FILE_STABLE_FOR
export FILE_STABLE_INTERVAL
export KCC_TIMEOUT

exec python3 /app.py
