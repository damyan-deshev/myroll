from __future__ import annotations

import argparse
from pathlib import Path

from backend.app.storage_export import StorageExportError, restore_export_archive


def main() -> None:
    parser = argparse.ArgumentParser(description="Restore a Myroll export archive into a data directory.")
    parser.add_argument("archive", type=Path)
    parser.add_argument("target_data_dir", type=Path)
    parser.add_argument("--force", action="store_true", help="Remove and replace a non-empty target directory.")
    args = parser.parse_args()

    try:
        target = restore_export_archive(args.archive, args.target_data_dir, force=args.force)
    except StorageExportError as error:
        raise SystemExit(f"{error.code}: {error.message}") from error

    print(f"Restored export into: {target}")
    print(f"Start with: MYROLL_DATA_DIR='{target}' scripts/start_dev.sh")


if __name__ == "__main__":
    main()
