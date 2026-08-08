# Changelog

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
