"""
ResearchPilot - Render Keepalive Daemon
Pings the Render backend and frontend every 12 minutes to prevent free-tier containers
from spinning down due to the 15-minute inactivity timeout.

Usage:
    python scripts/keepalive.py
"""

import time
import datetime
import urllib.request
import urllib.error

BACKEND_URL = "https://researchpilot-api-cb0c.onrender.com/api/v1/health"
FRONTEND_URL = "https://researchpilot-web.onrender.com"

# Render spins down after 15 minutes of inactivity; 12 minutes (720s) keeps it alive safely
PING_INTERVAL_SECONDS = 720


def ping(url: str, label: str) -> None:
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    start = time.time()
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "ResearchPilot-Keepalive/1.0"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            elapsed = time.time() - start
            print(f"[{now}] [OK] {label}: HTTP {resp.status} ({elapsed:.2f}s)")
    except urllib.error.HTTPError as e:
        elapsed = time.time() - start
        print(f"[{now}] [HTTP {e.code}] {label}: {e.reason} ({elapsed:.2f}s)")
    except Exception as e:
        elapsed = time.time() - start
        print(f"[{now}] [FAIL] {label}: {e} ({elapsed:.2f}s)")


def main():
    print("=" * 60)
    print(" ResearchPilot Render Keepalive Daemon")
    print(f" Interval: Every {PING_INTERVAL_SECONDS // 60} minutes")
    print(f" Backend Target:  {BACKEND_URL}")
    print(f" Frontend Target: {FRONTEND_URL}")
    print(" Press Ctrl + C to stop.")
    print("=" * 60)

    while True:
        ping(BACKEND_URL, "Backend ")
        ping(FRONTEND_URL, "Frontend")
        print(f"Sleeping for {PING_INTERVAL_SECONDS // 60} minutes...\n")
        time.sleep(PING_INTERVAL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nKeepalive daemon stopped by user.")

