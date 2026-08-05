# KCC Dropbox Webhook

Questo add-on riceve un path di un nuovo capitolo scaricato da Suwayomi,
lo converte con Kindle Comic Converter per Kobo Aura e lo carica su Dropbox.

## Endpoint

POST /convert

Body JSON:
```json
{
  "file_path": "/share/suwayomi/downloads/mangas/TuttoAnimeManga (IT)/One Piece/TuttoAnimeManga_Ch.1189.cbz"
}
