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

### `POST /sync`

Riconcilia la cartella locale con quella Dropbox. Per ogni file sorgente sotto `watch_root` calcola il nome che avrebbe una volta convertito e lo cerca su Dropbox:

- **mancanti** → accodati per la conversione (job con `origin: sync`);
- **orfani** → file caricati dall'add-on che nessun capitolo locale rivendica più (capitolo cancellato, oppure nome cambiato dopo una modifica di `pad_chapter_digits` o `source_in_title`). Vengono cancellati solo se `sync_delete_orphans` è attiva.

Body opzionale:

```json
{ "dry_run": true, "force": false }
```

`dry_run` mostra il piano senza convertire né cancellare. `force` supera `sync_delete_limit`. Risponde `409` se una sincronizzazione è già in corso.

Con `sync_on_convert: true` la stessa riconciliazione parte automaticamente dopo ogni conversione arrivata dal webhook.

#### Cosa può cancellare

Gli upload vengono registrati in `/data/uploads.json`: la sincronizzazione cancella **solo** file che l'add-on ha caricato. Quello che metti nella cartella Dropbox per conto tuo non viene mai toccato. I file caricati prima della 2.5.0 vengono adottati nel registro non appena corrispondono a un capitolo locale.

Tre protezioni contro le cancellazioni di massa:

| Protezione | Comportamento |
| --- | --- |
| `watch_root` assente | La sincronizzazione fallisce senza cancellare nulla (share non montata) |
| Nessun file sorgente trovato | Idem: tutti i capitoli sembrerebbero cancellati |
| Più di `sync_delete_limit` orfani | Cancellazione saltata e motivo nella risposta, serve `force` |

Se usi KoboCloud con `REMOVE_DELETED` attivo, le cancellazioni su Dropbox si propagano anche al reader.

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
| `upscale` | `true` | Passa `-u`: ingrandisce le pagine più piccole dello schermo mantenendo le proporzioni |
| `stretch` | `false` | Passa `-s`: riempie esattamente lo schermo, **senza** mantenere le proporzioni |
| `source_in_title` | `false` | Aggiunge la fonte Suwayomi a nome file e serie, evitando collisioni tra fonti diverse |
| `author` | — | Autore passato a KCC (`-a`). Se vuoto KCC scrive `KCC`. Ignorato se `force_creator_to_series` è attiva |
| `pad_chapter_digits` | `0` | Zero-padding del capitolo nel nome file (`4` → `Bleach 0050`). `0` disattiva |
| `force_creator_to_series` | `false` | Scrive il nome della serie anche come autore |
| `file_stable_timeout` | `180` | Secondi massimi di attesa della stabilità del file |
| `file_stable_for` | `5` | Secondi di dimensione invariata richiesti |
| `file_stable_interval` | `1` | Intervallo di polling in secondi |
| `kcc_timeout` | `1800` | Timeout della conversione KCC |
| `notify_on_success` | `false` | Invia una notifica Home Assistant a conversione riuscita |
| `notify_service` | — | Servizio da chiamare, es. `notify.mobile_app_pixel` |
| `sync_on_convert` | `false` | Riconcilia con Dropbox dopo ogni conversione dal webhook |
| `sync_delete_orphans` | `false` | Permette alla sincronizzazione di cancellare da Dropbox i file senza capitolo locale |
| `sync_delete_limit` | `50` | Oltre questo numero di orfani la cancellazione viene saltata, salvo `force` |
| `keep_local_outputs` | `false` | Se `false`, elimina il file convertito da `output_dir` dopo l'upload riuscito su Dropbox per evitare l'accumulo infinito di spazio su disco |
| `max_job_history` | `100` | Numero massimo di job completati o falliti mantenuti in memoria (previene memory leak) |

## Più fonti per lo stesso manga

Il nome della serie viene ricavato dalla cartella del manga, quindi la fonte Suwayomi (`mangas/<fonte>/<manga>/`) è normalmente ignorata. Se scarichi lo stesso manga da due fonti, i nomi generati coincidono e l'upload successivo **sovrascrive** il precedente senza errori, perché Dropbox viene scritto in `WriteMode.overwrite`.

Con `source_in_title: true` la fonte entra nel nome file e nel nome serie:

```
Bleach 50 [Mangaworld (IT)].kepub.epub   serie: Bleach [Mangaworld (IT)]
Bleach 50 [MangaDex].kepub.epub          serie: Bleach [MangaDex]
```

L'indice di capitolo resta numerico, quindi l'ordinamento dentro ogni serie è invariato. Se il manga sta direttamente sotto `watch_root` (senza livello fonte), non viene aggiunto nessun suffisso.

## Raggruppamento per serie sul Kobo

Il firmware Kobo **non** legge i metadati di serie dai libri sideloaded: le colonne `Series` del database vengono popolate solo per i libri acquistati dallo store. Per questo l'add-on scrive comunque i metadati corretti, ma il Kobo da solo li ignora — da cui l'esistenza di `force_creator_to_series`, che usa il campo autore come raggruppamento di fortuna.

Per avere il raggruppamento vero serve un mod lato dispositivo, [NickelSeries](https://pgaskin.net/kobo-mods/NickelSeries/): si copia `KoboRoot.tgz` nella cartella `.kobo` e si riavvia. Legge sia `calibre:series`/`calibre:series_index` sia i campi EPUB3 `belongs-to-collection`/`group-position` — entrambi già scritti da questo add-on, con Calibre che ha la precedenza.

Funziona anche con i file che non arrivano da USB: l'hook è su `EPubParser::parse`, cioè sul parser dei metadati, quindi vale per qualunque libro che nickel analizza. Verificato con una libreria sincronizzata via KoboCloud, dove il rescan finale (`qndb ... pfmRescanBooksFull`) è sufficiente a far agganciare i metadati.

Con NickelSeries installato puoi rimettere `force_creator_to_series: false`, ma valorizza anche `author`: senza `-a` KCC scrive `KCC` come autore, quindi disattivare l'escamotage senza impostare un autore peggiora il campo invece di sistemarlo.

Se il raggruppamento per serie funziona, `pad_chapter_digits` non serve: la scheda Serie ordina per numero di capitolo. Serve solo se resti sull'ordinamento alfabetico per titolo, dove `Bleach 1189` precede `Bleach 50`.

## Pagine troppo piccole sul reader

KCC ridimensiona le immagini alla risoluzione del profilo dispositivo, ma per default **non ingrandisce** quelle più piccole: restano a dimensione nativa e appaiono centrate e piccole. Il problema si nota passando a un dispositivo con più pixel (Kobo Aura 758×1024 → Kobo Aura ONE 1404×1872): le stesse scansioni che prima venivano ridotte a schermo pieno ora sono sotto la risoluzione del pannello.

Se nei log compare:

```
WARNING: More than 25% of images are smaller than target device resolution.
```

tieni `upscale: true`. Usa `stretch` solo se accetti la deformazione delle proporzioni.

Nota sui formati: `format: KEPUB` esegue KCC con `-f EPUB`, perché è il profilo Kobo a far produrre l'estensione `.kepub.epub`; `KEPUB` non è un valore di formato valido per KCC.

## Note

L'endpoint non è autenticato: la porta 5005 va tenuta sulla rete locale e non esposta su Internet.
