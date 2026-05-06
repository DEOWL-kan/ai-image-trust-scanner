from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.report_center import bootstrap_sqlite_from_history  # noqa: E402
from app.services.report_store import REPORT_DB_PATH, count_reports, init_db  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Import legacy API history JSON records into the Day29 reports SQLite store.")
    parser.add_argument(
        "--history-dir",
        default=str(PROJECT_ROOT / "outputs" / "api_history"),
        help="Directory containing legacy single/batch API history JSON files.",
    )
    args = parser.parse_args()

    init_db()
    imported = bootstrap_sqlite_from_history(Path(args.history_dir))
    print(f"reports_db={REPORT_DB_PATH}")
    print(f"imported={imported}")
    print(f"total={count_reports()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
