# collections-backup-utility

For the Alma Extensibility Task Force.

This utility backs up electronic collections and subcollections across the CUNYs each
month. For every (sub)collection it saves a CSV of the MMS IDs of all items within it,
plus a `COLLECTIONS.xml` dump per college. Suppressed collections are not captured.

## How it works

The job makes many sequential (idempotent) GET requests to the Alma API, so it can be
long-running. It is designed to be **interrupted and resumed** — e.g. when a laptop
sleeps mid-run — without losing or duplicating data:

- Output is written under `data/YYYY-MM/<college>/` — keyed to the **month**, so a run
  that starts on one day and finishes on another lands in the same place.
- Each collection's CSV is written **atomically** (to a `.tmp` file, then renamed). A
  CSV therefore exists only when it is complete, so on resume a present CSV is skipped
  and a missing one is (re)fetched.
- `COMPLETE` marker files record finished work: one per college, and one per month.
  Once the month's `COMPLETE` marker exists, the job is a fast **no-op**.
- Transient network errors (timeouts, dropped connections) are retried with backoff.

Because every run targets the current month and resumes from disk, a **daily** timer is
all that's needed: the first run of the month does the work, an interrupted run is
finished by the next day's trigger, and subsequent runs do nothing until the next month.

## Configuration

Create a `.env` file in the project root with one `college=apikey` pair per line
(this file is git-ignored — do not commit API keys):

```
Hunter=YOUR_ALMA_API_KEY
Brooklyn=YOUR_ALMA_API_KEY
```

## Running manually

```bash
uv sync                       # create the venv / install deps
uv run python -m collections_backup
```

(`python backup.py` still works as a thin compatibility shim.)

## Running on a schedule (systemd, user units)

Unit files live in [`systemd/`](systemd/). Install them as **user** units so they run
under your login on a laptop:

```bash
mkdir -p ~/.config/systemd/user
cp systemd/collections-backup.service ~/.config/systemd/user/
cp systemd/collections-backup.timer   ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now collections-backup.timer
```

Check status / logs:

```bash
systemctl --user list-timers collections-backup.timer
journalctl --user -u collections-backup.service -e
```

The `.service` assumes the repo is at `~/git/collections-backup-utility` and that `uv`
is at `/snap/bin/uv`; adjust `WorkingDirectory`/`ExecStart` if yours differ.

Optional:

- To keep the timer running even when you're logged out: `loginctl enable-linger $USER`.
- To discourage the laptop from sleeping while a backup is in progress, wrap the command:
  `ExecStart=/usr/bin/systemd-inhibit --what=sleep /snap/bin/uv run python -m collections_backup`.

## Development

Tests use `pytest` with the network mocked via `httpx.MockTransport` (no live API calls):

```bash
uv run pytest
```

Formatting is `black`. All backup logic lives in `src/collections_backup/core.py`; the
functions take an injected HTTP client and date so they're unit-testable.
