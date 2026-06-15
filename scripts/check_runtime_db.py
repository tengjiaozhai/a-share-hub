"""CLI database readiness check.

Usage:
    /opt/anaconda3/envs/py311/bin/python3 scripts/check_runtime_db.py

Exit codes:
    0 — database reachable
    1 — database unreachable
"""

import sys

from src.storage.health import probe_runtime_database_from_settings


def main() -> int:
    result = probe_runtime_database_from_settings()
    if result["ok"]:
        print(f"ok latency_ms={result['latency_ms']}")
        return 0
    print(f"error latency_ms={result['latency_ms']} detail={result['error']}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
