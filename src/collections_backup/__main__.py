"""Entrypoint: wire real config + HTTP client and run the backup for this month.

Run with ``python -m collections_backup`` (this is what the systemd unit calls).
Reads ``.env`` (``college=apikey`` per line) from the current working directory.
"""

from datetime import date
from pathlib import Path

import dotenv
import httpx

from collections_backup import core

# Generous per-request timeout: some Alma collection listings are large.
TIMEOUT = httpx.Timeout(500.0)


def main() -> None:
    config = dotenv.dotenv_values(".env")
    today = date.today()
    print(f"Backing up collections for {core.month_key(today)}...")
    with httpx.Client(timeout=TIMEOUT) as client:
        core.run(client, config, today, Path("data"))
    print("Done.")


if __name__ == "__main__":
    main()
