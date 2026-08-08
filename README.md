# KCC Dropbox Webhook

Add-on Home Assistant che espone un webhook HTTP per convertire i download di Suwayomi con Kindle Comic Converter (KCC) e caricare automaticamente il file risultante su Dropbox.

Il flusso è pensato per ebook reader Kobo e usa i profili dispositivo di KCC per generare EPUB, KEPUB o CBZ.

## Come funziona

1. Un client invia una richiesta HTTP `POST /convert` con il percorso del file sorgente dentro la share di Home Assistant.
2. L'add-on verifica che il file sia sotto `watch_root` e aspetta che la dimensione sia stabile prima di elaborarlo.
3. Il file viene convertito con KCC usando il profilo Kobo configurato e il formato richiesto.
4. Il risultato viene rinominato, arricchito con metadati di serie/capitolo e caricato nella cartella Dropbox configurata.

## Endpoint

### `POST /convert`

Body JSON di esempio:

```json
{
  "file_path": "/share/suwayomi/downloads/mangas/TuttoAnimeManga (IT)/One Piece/TuttoAnimeManga_Ch.1189.cbz"
}
