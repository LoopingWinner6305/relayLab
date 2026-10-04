# RelayLab — webhook relay, v0.1

A local backend prototype that accepts a sensor event, persists it, forwards it
to a demonstration HTTP receiver through a separate worker, and records the
delivery result. The sensor example connects this backend project to ECE;
the relay does not require real hardware.

**Current status:** assisted starter implementation; ongoing learning project.
This repository demonstrates a small working flow, not a production service.

## Workflow

```text
Browser or API client
        |
        | POST /events
        v
FastAPI --> SQLite [event + pending job in one transaction]
                         |
                         | one Python worker polls the database
                         v
                   HTTP demo receiver
                         |
                         v
               SQLite [attempt + delivered/failed status]
                         |
                         v
               GET /events/{id} or dashboard
```

## Included now

- FastAPI request validation and interactive API docs.
- SQLite persistence for events, jobs, and delivery attempts.
- Identical submissions with the same ID reuse the existing event; changed
  content with that ID returns HTTP 409. This deduplicates API submissions.
- Separate worker with a three-second HTTP timeout and recorded HTTP/network errors.
- Local receiver with a successful endpoint and an intentional HTTP 503 endpoint.
- Plain HTML dashboard to submit sensor readings and inspect recent events.
- Tests for persistence, duplicate submissions, HTTP delivery, failures, and API validation.
- GitHub Actions configuration to run the tests when uploaded.

Local verification on October 4, 2026: **8 tests passed** on Python 3.12,
including actual HTTP delivery to a temporary local receiver. There was one
dependency deprecation warning about the test client's use of `httpx`.
The main dependency versions are pinned to the versions used for this check.
GitHub Actions has not been run here; it will run after you push the repository.

## Start on Windows (Python 3.11+)

Open a terminal **inside the folder containing this README**. Run:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Then open three terminals in that same folder. No virtual-environment activation is required.

Terminal 1 — API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn relaylab.api:app --host 127.0.0.1 --port 8000
```

Terminal 2 — demo receiver:

```powershell
.\.venv\Scripts\python.exe -m uvicorn relaylab.receiver:app --host 127.0.0.1 --port 8001
```

Terminal 3 — **one** worker:

```powershell
.\.venv\Scripts\python.exe -m relaylab.worker
```

Open http://127.0.0.1:8000, click **Send new sensor event**, wait a second,
then click **Refresh events**. Its status should become `delivered`.
Open http://127.0.0.1:8001/received to inspect the actual received payload.
The API documentation is at http://127.0.0.1:8000/docs.

On macOS/Linux use `python3` for environment creation and `.venv/bin/python`
in place of `.\.venv\Scripts\python.exe`.

## Five-minute manual demonstration

With all three processes running, use a fourth PowerShell terminal:

```powershell
$event = @{ id = 'demo-001'; event_type = 'sensor.reading'; payload = @{ temperature_c = 28.4 } } | ConvertTo-Json -Depth 5
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/events -ContentType 'application/json' -Body $event
Start-Sleep -Seconds 1
Invoke-RestMethod -Uri http://127.0.0.1:8000/events/demo-001 | ConvertTo-Json -Depth 6
```

1. Inspect the `delivered` status and HTTP 200 attempt.
2. Submit the same `$event` again. `created` is false; no extra job is created.
3. Stop the receiver with Ctrl+C. Submit a **new ID**, such as `demo-002`.
   Its status becomes `failed`, with a network error recorded.
4. Restart the receiver. Submit another new ID; it should be delivered.
5. Stop/restart the API. Existing events remain because SQLite stores them on disk.

For an explicit HTTP failure, stop the worker, then restart it as follows:

```powershell
$env:RELAYLAB_RECEIVER_URL = 'http://127.0.0.1:8001/fail'
.\.venv\Scripts\python.exe -m relaylab.worker
```

New events fail with HTTP 503 recorded. Stop that worker and run
`Remove-Item Env:RELAYLAB_RECEIVER_URL` before restarting the successful demo.
Failed jobs are not automatically retried in v0.1.

## Read the code in this order

1. `relaylab/api.py`: validate input, store it, return its state.
2. `relaylab/store.py`: understand the three tables and transaction boundaries.
3. `relaylab/worker.py`: follow one pending event through HTTP delivery and recording.
4. `relaylab/receiver.py`: inspect the receiving side.
5. `tests/test_workflow.py`: see delivery tested against a real local HTTP server.
6. `tests/test_api.py`: see validation and duplicate handling tested through the API.

## Limits to explain accurately

- SQLite, not PostgreSQL. This deliberately reduces installation work for v0.1.
- One worker only. Multiple workers can pick the same pending job.
- One recorded attempt per event in normal execution; no retry scheduling or manual replay.
- A crash after HTTP delivery but before recording the result can cause redelivery
  on restart. Submission deduplication does **not** guarantee exactly-once delivery.
- The receiver keeps only its last 100 receipts in memory; restarting it clears them.
- No authentication, webhook signatures, rate limits, payload-size limits, migrations,
  or retention policy. Run locally with non-sensitive example data.
- The receiver URL is configured by the operator, not supplied by incoming events.
  Redirects are refused. There is no arbitrary destination subscription API.
- The dashboard is plain HTML/JavaScript; React, Docker and cloud deployment are future work.

## Continue after exams

Make each improvement a separate commit, with a corresponding test:

1. Explain the present flow without reading notes. Change the sample event to a
   device heartbeat and add one validation test you understand.
2. Add scheduled retries: `attempt_count`, `next_attempt_at`, a maximum attempt
   count, and exponential backoff. Prove that retries eventually stop.
3. Add receiver-side idempotency using persistent event IDs; demonstrate how it
   prevents repeated side effects when delivery is repeated.
4. Move storage to PostgreSQL, add migrations, and implement safe job claiming
   before running two workers. Test that they do not both claim the same job.
5. Add HMAC signature creation/verification, then authentication for submission.
6. Add Docker Compose and improve the dashboard only after the backend behavior
   is understood and tested.

## Upload to GitHub

Create an empty repository named `relaylab` on your GitHub account. From this
folder, replacing `YOUR_USERNAME` with your actual username:

```powershell
git init
git add .
git commit -m "Add RelayLab v0.1 webhook relay prototype"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/relaylab.git
git push -u origin main
```

`.gitignore` excludes the local database, virtual environment, and `.env` files.
Check the GitHub Actions run after pushing; its result is separate from local tests.

## CV wording — only after you run and understand the demo

**RelayLab — webhook relay prototype (in progress)** | Python, FastAPI, SQLite

> Built and tested an initial webhook relay flow with persistent event storage,
> duplicate submission handling, a separate delivery worker, and recorded HTTP
> delivery outcomes. Extending the prototype with retries and PostgreSQL.

Use “Built” only if you can explain the implementation and have made it your own;
otherwise use “Developing” and describe this as an assisted starter. Do not list
future PostgreSQL, retries, Docker, React or deployment as completed features.
Do not claim traffic scale, performance measurements, or production use.
