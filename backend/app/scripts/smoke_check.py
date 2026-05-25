from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Easy MES HTTP smoke checks.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080", help="Frontend or backend base URL.")
    parser.add_argument("--timeout", type=float, default=5.0, help="Request timeout in seconds.")
    return parser.parse_args()


def check_endpoint(base_url: str, path: str, timeout: float) -> dict:
    url = f"{base_url.rstrip('/')}{path}"
    with urllib.request.urlopen(url, timeout=timeout) as response:
        if response.status >= 400:
            raise RuntimeError(f"{url} returned HTTP {response.status}")
        return json.loads(response.read().decode())


def main() -> int:
    args = parse_args()
    try:
        health = check_endpoint(args.base_url, "/api/v1/health", args.timeout)
        readiness = check_endpoint(args.base_url, "/api/v1/health/ready", args.timeout)
    except (RuntimeError, urllib.error.URLError, TimeoutError) as exc:
        print(f"smoke check failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"health": health, "readiness": readiness}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
