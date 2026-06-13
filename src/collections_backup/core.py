"""Core logic for the collections backup utility.

All network I/O takes an injected ``httpx.Client`` and all clock access takes an
injected ``today``/``sleep`` so the whole module is unit-testable without touching
the network or the wall clock.
"""

import os
import time
from datetime import date
from pathlib import Path

import httpx

# Alma API endpoints / query fragments (the api key is appended by the caller).
_COLLECTIONS = (
    "https://api-na.hosted.exlibrisgroup.com/almaws/v1/bibs/collections?level=20"
)
COLLECTIONS_JSON = _COLLECTIONS + "&format=json&apikey="
COLLECTIONS_XML = _COLLECTIONS + "&apikey="
BIBS_PARAMS = "/bibs?level=2&format=json&limit=100&apikey="
PAGE_SIZE = 100


def month_key(today: date) -> str:
    """Return the stable, month-granular key for a run, e.g. ``"2026-06"``."""
    return today.strftime("%Y-%m")


def sanitize_name(name: str) -> str:
    """Replace ``/`` with ``.`` so collection names don't break file paths."""
    return name.replace("/", ".")


def collection_csv_path(base: Path, college: str, name: str, mms_id: str) -> Path:
    """Build the CSV path for one collection: ``<base>/<college>/<name>-<id>.csv``."""
    return Path(base) / college / f"{sanitize_name(name)}-{mms_id}.csv"


def flatten_collections(data: dict) -> list[dict]:
    """Flatten the nested collection tree into one entry per collection node.

    Subcollections are emitted before their parent (matching the original
    recursive walk). Each entry is ``{"name", "mms_id", "pid_link"}``; a node
    without a ``pid`` link still appears (it yields a header-only CSV, as before).
    A payload with no ``"collection"`` key yields ``[]`` (the original
    "No collections found." early-out).
    """
    flat: list[dict] = []
    for node in data.get("collection", []):
        flat.extend(flatten_collections(node))
        pid = node.get("pid")
        flat.append(
            {
                "name": node["name"],
                "mms_id": node["mms_id"]["value"],
                "pid_link": pid["link"] if pid else None,
            }
        )
    return flat


def mmsids_from_page(data: dict) -> list[str]:
    """Extract the MMS IDs from one page of a ``/bibs`` response."""
    return [bib["mms_id"] for bib in data.get("bib", [])]


def get_with_retries(
    client: httpx.Client,
    url: str,
    *,
    retries: int = 3,
    backoff: float = 1.0,
    sleep=time.sleep,
) -> httpx.Response:
    """GET ``url`` with bounded retries and exponential backoff.

    Retries only transient transport errors (timeouts, dropped connections) —
    safe because every request is an idempotent GET. Sleeps ``backoff * 2**n``
    between attempts and re-raises the last error once ``retries`` is exhausted.
    """
    for attempt in range(retries):
        try:
            return client.get(url)
        except httpx.TransportError:
            if attempt == retries - 1:
                raise
            sleep(backoff * (2**attempt))


def fetch_all_mmsids(
    client: httpx.Client, pid_link, key: str, *, get=get_with_retries
) -> list[str]:
    """Page through a collection's ``/bibs`` endpoint, collecting every MMS ID.

    Returns ``[]`` (no network calls) when the collection has no ``pid`` link.
    Stops once a page yields no MMS IDs.
    """
    if not pid_link:
        return []
    mmsids: list[str] = []
    offset = 0
    while True:
        url = f"{pid_link}{BIBS_PARAMS}{key}&offset={offset}"
        page = get(client, url).json()
        ids = mmsids_from_page(page)
        if not ids:
            return mmsids
        mmsids.extend(ids)
        offset += PAGE_SIZE


def _atomic_write_text(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` atomically (full write to ``*.tmp``, then rename).

    The final file exists only once it is complete — the property that makes a
    half-finished run safe to resume: a present file is always a finished file.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def write_csv_atomic(path: Path, mmsids: list[str]) -> None:
    """Write the MMS-ID CSV (``MMS ID`` header + one id per line) atomically."""
    _atomic_write_text(path, "MMS ID\n" + "".join(mmsid + "\n" for mmsid in mmsids))


def backup_college(
    client: httpx.Client,
    month_base: Path,
    college: str,
    key: str,
    *,
    get=get_with_retries,
) -> None:
    """Back up one college, skipping work already on disk.

    Resume is driven entirely by file presence: a ``COMPLETE`` marker skips the
    whole college, and an existing per-collection CSV skips that collection.
    """
    college_dir = Path(month_base) / college
    complete = college_dir / "COMPLETE"
    if complete.exists():
        return

    xml_path = college_dir / "COLLECTIONS.xml"
    if not xml_path.exists():
        _atomic_write_text(xml_path, get(client, COLLECTIONS_XML + key).text)

    listing = get(client, COLLECTIONS_JSON + key).json()
    for coll in flatten_collections(listing):
        csv_path = collection_csv_path(
            month_base, college, coll["name"], coll["mms_id"]
        )
        if csv_path.exists():
            continue
        mmsids = fetch_all_mmsids(client, coll["pid_link"], key, get=get)
        write_csv_atomic(csv_path, mmsids)

    complete.touch()


def run(
    client: httpx.Client,
    config: dict,
    today: date,
    base_dir: Path,
    *,
    get=get_with_retries,
) -> None:
    """Back up every college for the current month, resuming if interrupted.

    No-op once the month's top-level ``COMPLETE`` marker exists, so a daily timer
    can fire harmlessly after the month's backup is done.
    """
    base = Path(base_dir) / month_key(today)
    if (base / "COMPLETE").exists():
        return
    for college, key in config.items():
        backup_college(client, base, college, key, get=get)
    base.mkdir(parents=True, exist_ok=True)
    (base / "COMPLETE").touch()
