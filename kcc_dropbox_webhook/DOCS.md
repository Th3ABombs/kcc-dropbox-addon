# KCC Dropbox Webhook

Questo add-on riceve il path di un nuovo capitolo scaricato da Suwayomi, lo
converte con Kindle Comic Converter per il Kobo configurato e lo carica su
Dropbox.

## Configurazione

Le credenziali Dropbox (`dropbox_app_key`, `dropbox_app_secret`,
`dropbox_refresh_token`) sono obbligatorie: senza di esse la conversione va a
buon fine ma l'upload fallisce. `watch_root` delimita i path accettati,
`output_dir` è la cartella di lavoro dei file convertiti.

Per le notifiche imposta `notify_on_success: true` e `notify_service` con un
servizio `notify.*` (es. `notify.mobile_app_pixel`).

L'elenco completo delle opzioni è nel README del repository.

## Endpoint

### POST /convert

Body JSON:

```json
{
  "file_path": "/share/suwayomi/downloads/mangas/TuttoAnimeManga (IT)/One Piece/TuttoAnimeManga_Ch.1189.cbz"
}
```

Risponde `202` con un `job_id`. Il file viene accodato ed elaborato da un worker
in background, un job alla volta.

Esempio di automazione Home Assistant:

```yaml
action: rest_command.kcc_convert
data:
  file_path: "{{ trigger.event.data.path }}"
```

```yaml
rest_command:
  kcc_convert:
    url: "http://localhost:5005/convert"
    method: POST
    content_type: "application/json"
    payload: '{"file_path": "{{ file_path }}"}'
```

### GET /jobs/&lt;job_id&gt;

Stato del job: `queued`, `processing`, `done`, `error`. In caso di errore il
campo `error` contiene stdout/stderr di KCC.

### GET /jobs, GET /queue, GET /health

Rispettivamente: storico dei job, coda corrente, configurazione attiva e stato
del worker. `/health` è la Web UI dell'add-on e non espone i segreti.

## Note

L'endpoint non richiede autenticazione: non esporre la porta 5005 su Internet.
