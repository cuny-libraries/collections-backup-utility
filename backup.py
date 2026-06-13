"""Backwards-compatible shim. The implementation now lives in the
``collections_backup`` package; run ``python -m collections_backup`` instead."""

from collections_backup.__main__ import main

if __name__ == "__main__":
    main()
