# RelayLab

RelayLab is a webhook relay built with Python, FastAPI, and SQLite. It accepts
events through an API, stores them, and forwards them to an HTTP receiver using
a separate worker. Delivery results are recorded and can be inspected through
the API or a browser dashboard.

Version 0.1 implements the basic delivery flow. The demo uses simulated sensor
readings; no hardware is required.

## Workflow

```text
Client submits an event
        |
        v
FastAPI validates the request
        |
        v
SQLite stores the event and a pending delivery job
        |
        v
Worker sends the event to the receiver
        |
        v
SQLite records the attempt and delivery status
        |
        v
Client checks the result through the API or dashboard
```

The event and its delivery job are created in the same database transaction.
The worker polls for pending jobs and marks each one as `delivered` or `failed`.

## Features

- Request validation and interactive API documentation.
- Persistent storage for events, delivery jobs, and attempts.
- Duplicate submission handling based on event IDs.
- A separate delivery worker with a three-second HTTP timeout.
- Recorded HTTP errors, timeouts, and connection failures.
- A demo receiver with success and failure endpoints.
- A browser dashboard for submitting events and checking their status.
- Tests covering API behavior, persistence, and HTTP delivery.

## Getting started

Requires **Python 3.11 or newer**. Run commands from the repository root.
If your system uses `python3` instead of `python`, use it to create the virtual
environment below.

### 1. Create a virtual environment

```sh
python -m venv .venv
```

Activate it using the command for your terminal.

**Windows PowerShell**

```powershell
.\.venv\Scripts\Activate.ps1
```

**Windows Command Prompt**

```bat
.venv\Scripts\activate.bat
```

**Linux / macOS**

```sh
source .venv/bin/activate
```

### 2. Install dependencies

```sh
python -m pip install -r requirements-dev.txt
```

For running the application without the test dependencies, use `requirements.txt`.

### 3. Start the processes

Open three terminals in the repository root and activate the virtual environment
in each one.

**API**

```sh
python -m uvicorn relaylab.api:app --host 127.0.0.1 --port 8000
```

**Demo receiver**

```sh
python -m uvicorn relaylab.receiver:app --host 127.0.0.1 --port 8001
```

**Worker**

```sh
python -m relaylab.worker
```

Run only one worker. Stop a process with **Ctrl+C**.

| Page | URL |
| --- | --- |
| Dashboard | http://127.0.0.1:8000 |
| API documentation | http://127.0.0.1:8000/docs |
| Receiver receipts | http://127.0.0.1:8001/received |

## Trying the relay

1. Open the dashboard and click **Send new sensor event**.
2. Wait a second, then click **Refresh events**. The status should be `delivered`.
3. Open the receiver receipts page to inspect the received payload.
4. Stop the receiver and submit a new event. It should become `failed`.
5. Restart the receiver and submit another new event to check successful delivery.

Use `GET /events/{event_id}` in the API documentation to inspect an event's
delivery attempts. Restarting the API preserves the stored events and attempts.

For duplicate handling, submit this body twice through `POST /events` in the
API documentation:

```json
{
  "id": "demo-001",
  "event_type": "sensor.reading",
  "payload": {
    "temperature_c": 28.4
  }
}
```

A new event returns HTTP `201`. An identical submission with the same ID returns
HTTP `200` with `created: false`, without creating another delivery job. Reusing
the ID with different content returns HTTP `409`.

The demo receiver also provides `POST /fail`, which always returns HTTP `503`.
Set the worker's `RELAYLAB_RECEIVER_URL` to `http://127.0.0.1:8001/fail` to test
an HTTP failure while keeping the receiver running.

## API endpoints

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | Basic API health response |
| `POST` | `/events` | Submit an event |
| `GET` | `/events` | List recent events, newest first |
| `GET` | `/events/{event_id}` | Retrieve an event and its delivery attempts |

`GET /events` accepts a `limit` query parameter from 1 to 100; the default is 50.
Missing events return HTTP `404`. Invalid request bodies return HTTP `422`.

## Configuration

| Environment variable | Default | Purpose |
| --- | --- | --- |
| `RELAYLAB_DB` | `data/relaylab.sqlite3` | SQLite database location |
| `RELAYLAB_RECEIVER_URL` | `http://127.0.0.1:8001/webhook` | Worker's delivery destination |

Set environment variables before starting the relevant process. The API and
worker must use the same database file. Relative paths are resolved from each
process's working directory.

## Tests

With the development dependencies installed and the virtual environment active:

```sh
python -m pytest -q
```

The tests cover request validation, duplicate handling, conflicting event IDs,
persistence, successful delivery, HTTP errors, and connection failures. Delivery
tests use a temporary database and a local HTTP server.

The workflow in `.github/workflows/tests.yml` runs the suite on pushes and
pull requests.

## Project structure

```text
relaylab/
  api.py            Request models and API endpoints
  store.py          Database schema, transactions, and queries
  worker.py         HTTP delivery and attempt recording
  receiver.py       Local demo receiver
  dashboard.html    Event submission and status view
tests/
  test_api.py       API and demo receiver tests
  test_workflow.py  Storage and delivery tests
```

## Current limitations

- Only one worker and one configured receiver are supported. Multiple workers
  can select the same pending job.
- Failed jobs are not retried, and there is no manual replay endpoint.
- A worker crash after delivery but before recording the result can cause
  redelivery on restart. Duplicate submission handling does not guarantee
  exactly-once delivery.
- The demo receiver keeps its latest 100 receipts in memory; restarting it clears
  that history. Relay events and attempts remain in SQLite.
- Authentication, webhook signatures, rate limits, payload-size limits, and data
  retention are not implemented. The default setup runs locally.

## Planned work

- Scheduled retries with backoff and an attempt limit.
- Persistent receiver-side deduplication.
- PostgreSQL storage with safe job claiming for multiple workers.
- Webhook signatures and API authentication.
