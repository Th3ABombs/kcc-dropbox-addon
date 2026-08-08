# KCC Dropbox Webhook

Add-on Home Assistant che espone un webhook HTTP per convertire i download di Suwayomi con Kindle Comic Converter (KCC) e caricare automaticamente il file risultante su Dropbox.

Il flusso è pensato per ebook reader Kobo e usa i profili dispositivo di KCC per generare EPUB, KEPUB o CBZ.

## Come funziona

1. Un client invia una richiesta HTTP `POST /convert` con il percorso del file sorgente dentro la share di Home Assistant.
2. L'add-on verifica che il file sia sotto `watch_root` e aspetta che la dimensione sia stabile prima di elaborarlo.
3. Il file viene convertito con KCC usando il profilo Kobo configurato e il formato richiesto.
4. Il risultato viene rinominato, arricchito con metadati di serie/capitolo e caricato nella cartella Dropbox configurata.

Le richieste vengono accodate ed elaborate una alla volta da un worker in background: `POST /convert` risponde subito con un `job_id` da usare per seguire l'avanzamento.

## Endpoint

### `POST /convert`

Body JSON di esempio:

```json
{
  "file_path": "/share/suwayomi/downloads/mangas/TuttoAnimeManga (IT)/One Piece/TuttoAnimeManga_Ch.1189.cbz"
}
```

Risposte:

| Codice | `status` | Significato |
| --- | --- | --- |
| 202 | `queued` | Job accodato, il body contiene `job_id` |
| 202 | `already_queued` | Lo stesso file è già in coda o in elaborazione |
| 202 | `ignored` | File temporaneo (`.part`, `.crdownload`, nomi che iniziano con `.`) |
| 400 | `error` | `file_path` mancante, JSON non valido o file inesistente |

### `GET /jobs/<job_id>`

Stato di un singolo job: `queued`, `processing`, `done` o `error`. Se completato include `result` (nomi finali, path Dropbox, serie e indice); se fallito include `error` con l'output di KCC.

### `GET /jobs`

Tutti i job noti, dal più recente.

### `GET /queue`

Coda corrente: job accodati, job in elaborazione e stato del worker.

### `GET /health`

Configurazione attiva (senza segreti: le credenziali Dropbox sono esposte solo come booleani `*_configured`), profilo Kobo risolto, dimensione della coda e stato del worker. È anche la pagina impostata come Web UI dell'add-on.

## Nomi dei file generati

Il nome finale è `<cartella del manga> <capitolo>.<estensione>`, per esempio `One Piece 1189.kepub.epub`.

Il capitolo viene ricavato dal nome del file, nell'ordine:

1. marcatori espliciti (`Ch.1189`, `cap 12`, `v03 c012`);
2. capitoli speciali (`Extra 3`, `Oneshot`, `Side Story`);
3. numero in coda al nome;
4. ultimo numero libero, ignorando gli anni tra parentesi (`One Piece 1189 (2024).cbz` → capitolo `1189`).

Se KCC divide la conversione in più file, questi vengono caricati tutti con il suffisso ` Part N`.

## Opzioni

| Opzione | Default | Descrizione |
| --- | --- | --- |
| `output_dir` | `/share/kcc-output` | Cartella di lavoro per i file convertiti |
| `watch_root` | `/share/suwayomi/downloads/mangas` | I file fuori da questa cartella vengono rifiutati |
| `dropbox_folder` | `/Applicazioni/Kobo Cloud Sync` | Cartella Dropbox di destinazione |
| `dropbox_app_key` | — | Credenziali dell'app Dropbox |
| `dropbox_app_secret` | — | Credenziali dell'app Dropbox |
| `dropbox_refresh_token` | — | Refresh token OAuth2 |
| `kobo_device` | `Kobo Libra Colour` | Determina il profilo KCC |
| `format` | `KEPUB` | `EPUB`, `KEPUB` o `CBZ` |
| `manga_mode` | `true` | Passa `-m` a KCC (lettura destra→sinistra) |
| `force_creator_to_series` | `false` | Scrive il nome della serie anche come autore |
| `file_stable_timeout` | `180` | Secondi massimi di attesa della stabilità del file |
| `file_stable_for` | `5` | Secondi di dimensione invariata richiesti |
| `file_stable_interval` | `1` | Intervallo di polling in secondi |
| `kcc_timeout` | `1800` | Timeout della conversione KCC |
| `notify_on_success` | `false` | Invia una notifica Home Assistant a conversione riuscita |
| `notify_service` | — | Servizio da chiamare, es. `notify.mobile_app_pixel` |

## Note

L'endpoint non è autenticato: la porta 5005 va tenuta sulla rete locale e non esposta su Internet.
