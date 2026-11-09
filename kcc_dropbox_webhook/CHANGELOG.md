# Changelog

## 2.7.2
- Fixed chapter and manga matching on Suwayomi:
  - Added direct fast chapter lookup using `condition: { mangaId, chapterNumber }`.
  - Fixed GraphQL validation error on `manga.chapters`: removed invalid argument `(first: 10000)` on `MangaType.chapters` which caused queries to fail on standard Suwayomi servers.
  - Added `condition: { title }` and library search fallback (`condition: { inLibrary: true }`) for manga discovery.
  - Enhanced chapter matching to handle `#138`, `Ch. 138`, chapter number prefixes, and string representations.
  - Added direct mutation input shape fallback (`id`, `isRead`).

## 2.7.1
- Fixed Suwayomi chapter lookup for manga with many chapters (e.g. Bleach, One Piece):
  - Added native REST API `/api/v1/manga/{id}/chapters` retrieval to bypass GraphQL connection page limits.
  - Added `first: 10000` pagination parameter to GraphQL fallbacks.
  - Multi-candidate manga search: iterates through all matching manga entries in Suwayomi to find the correct series.
  - Robust chapter name matching: extracts chapter numbers and labels from full Italian titles (e.g. `Capitolo 272 - Titolo`).
  - Added detailed INFO logging showing matched manga ID and title.

## 2.7.0
- Added optional Suwayomi integration to automatically mark converted chapters as read (`isRead: true`) on Suwayomi after a successful upload to Dropbox (`suwayomi_mark_read`, default `false`).
- Added configuration options: `suwayomi_url`, `suwayomi_username`, `suwayomi_password`, and `suwayomi_token` (supports unauthenticated, HTTP Basic Auth, and JWT `ui_login`).
- Guaranteed safety: local manga chapter downloads on Suwayomi are never deleted by this add-on, preventing unwanted sync deletions on Dropbox.
- Added Suwayomi status reporting in job serialization and the `/health` endpoint.

## 2.6.3
- Added `log_level` configuration option (`trace`, `debug`, `info`, `warning`, `error`, default: `info`).
- Reduced default log verbosity at `info` level:
  - Repetitive file stability polling checks and internal cleanup events now log at `debug`.
  - Full KCC command stdout/stderr on successful conversions now log at `debug` (failures and timeouts still log at `error` level).
  - Werkzeug HTTP access logs silenced at `info` level to prevent log pollution from health-checks and status polls.
- Exposed `log_level` in `/health` endpoint.

## 2.6.2
- Fixed `ImportError: libglib-2.0.so.0: cannot open shared object file` by installing
  `libglib2.0-0`, `libgl1`, `libegl1`, `libdbus-1-3`, `libfontconfig1`, `libxext6`,
  `libxrender1` and `libxi6` in the Docker image, which are required by PySide6
  (used by KCC for translations and Qt runtime).
- Set `QT_QPA_PLATFORM=offscreen` to ensure Qt operates cleanly in headless Docker containers.

## 2.6.1
- Logged KCC stdout and stderr output on conversion errors and timeouts so the
  exact reason for conversion failures is immediately visible in the logs.
- Added automatic cleanup of previously-uploaded files from `output_dir` at
  startup and during `/sync` when `keep_local_outputs: false`, freeing up space
  occupied by older add-on versions.
- Reverted isolated `TMPDIR` override for KCC subprocess in favor of safe external
  cleanup of temporary folders in `/tmp`.

## 2.6.0
- Added the `keep_local_outputs` option (default `false`): automatically removes
  converted book files from `output_dir` after a successful upload to Dropbox,
  preventing unbounded disk space accumulation in `/share`.
- Added isolated temporary directories (`TMPDIR`) per KCC conversion process,
  ensuring all extracted images and temp files are cleanly purged even if KCC
  crashes or times out.
- Automatic cleanup of leftover `.staging-*` files in `output_dir` at startup
  and via `finally` blocks during conversion errors.
- Added cleanup of local orphan files in `output_dir` during `/sync` when
  `sync_delete_orphans` is enabled.
- Added `max_job_history` option (default `100`) and job history pruning to prevent
  unbounded memory growth in the Flask process.

## 2.5.0
- Added `POST /sync`, which reconciles the local Suwayomi folder with the
  Dropbox folder: chapters with no uploaded counterpart are queued for
  conversion, and files that no longer match any local chapter are reported
  (and deleted, when enabled). Accepts `dry_run` and `force`.
- Added the `sync_on_convert` option (default `false`): runs the same
  reconciliation after every webhook conversion. Jobs queued by a sync never
  trigger another one.
- Added the `sync_delete_orphans` (default `false`) and `sync_delete_limit`
  (default `50`) options.
- Uploads are now tracked in a persistent registry under `/data`, so the sync
  can only ever delete files this add-on uploaded. Files added to the Dropbox
  folder by other means are never touched. Files already uploaded before this
  version are adopted into the registry when they match a local chapter.
- The sync refuses to run when `watch_root` is missing or contains no source
  files, which would otherwise make every chapter look deleted.
- Job records and `/jobs` now include `origin` (`webhook` or `sync`).

## 2.4.0
- Added the `author` option, passed to KCC as `-a`. Without it KCC writes the
  literal string `KCC` as the author, which is what shows up in the library when
  `force_creator_to_series` is disabled. Ignored when
  `force_creator_to_series` is enabled, since the creator is overwritten with
  the series name.
- Added the `pad_chapter_digits` option (default `0`, disabled). Pads the
  chapter number in the filename and title, so that alphabetical sorting matches
  numerical order (`Bleach 1189` would otherwise sort before `Bleach 50`).
  The series index keeps the unpadded number, and special labels such as
  `Extra 3` are left untouched.

## 2.3.0
- Added the `source_in_title` option (default `false`). With multiple Suwayomi
  sources for the same manga the generated names were identical, because the
  source folder is not part of the name: the second upload silently overwrote
  the first, since Dropbox uploads use `WriteMode.overwrite`. When enabled, the
  source is appended to both the filename and the series name
  (`Bleach 50 [Mangaworld (IT)].kepub.epub`, series `Bleach [Mangaworld (IT)]`).
- `/health` reports `source_in_title`, and the job result includes `source`.

## 2.2.0
- Fixed the output never being a real KEPUB. KCC's `-f` accepts any string
  without validating it, so `-f KEPUB` was silently unrecognised: the conversion
  fell through to the generic EPUB branch and the file was written as `.epub`,
  because KCC only assigns the `.kepub.epub` extension when the format is
  exactly `EPUB` on a Kobo profile. On Kobo the extension selects the renderer,
  so pages were shown by the plain EPUB engine. `format: KEPUB` now runs
  `-f EPUB` (Kobo profile → `.kepub.epub`) and `format: EPUB` adds `--nokepub`.
- Added the `upscale` option (default `true`), which passes `-u` to KCC. Without
  it, pages smaller than the device resolution are left at native size and shown
  small and centred — very visible on high resolution devices such as the Kobo
  Aura ONE (1404x1872) compared to a Kobo Aura (758x1024).
- Added the `stretch` option (default `false`), which passes `-s` to KCC: fills
  the screen exactly but does not preserve the aspect ratio.
- Fixed `manga_mode: false` being ignored: in jq the `//` operator also discards
  `false`, so the option always evaluated to `true`.
- `/health` now reports `upscale`, `stretch` and the expected output extension.

## 2.1.3
- Fixed chapter detection picking a bracketed year instead of the chapter number
  (`One Piece 1189 (2024).cbz` was uploaded as chapter 2024).
- Fixed special chapter labels being ignored whenever the filename contained a
  digit (`Extra 3` was detected as chapter `3`).
- Special labels now keep their number: `Extra 3`, `Special 2`.
- Fixed the uploaded filename for decimal chapters: `Serie 97.5.kepub.epub` no
  longer becomes `Serie 97.5.5.kepub.epub`.
- Converted file detection now ignores directories and non-book files, detects
  files overwritten in place, and uploads every file when KCC splits the output
  into multiple parts (previously one arbitrary file was picked).
- Filenames are stripped of control characters and leading/trailing dots, and
  clamped in length.
- Smaller image: build toolchain removed at the end of the Docker build.
- Fixed the add-on URL in `config.yaml` and aligned the changelog version.

## 2.1.2
- Added Home Assistant notification support on successful conversion.
- Added notify_on_success and notify_service options.
- Improved metadata handling and runtime diagnostics.

## 2.0.5
- Added FORCE_CREATOR_TO_SERIES option.
- Improved series metadata injection for Kobo-compatible books.

## 1.0.0
- Prima versione.
- Webhook HTTP per conversione KCC.
- Supporto Kobo Aura.
- Upload automatico su Dropbox.
