#!/usr/bin/env python3
"""
Minimal local price watcher (no cloud, no tracking).

Features
- Reads products from products.yaml (URL, CSS selector for price, target price).
- Fetches pages with a desktop User-Agent.
- Parses price text using CSS selector (BeautifulSoup).
- Normalizes to a float (USD-style or international formats).
- Saves every check into SQLite (price_history.db).
- Prints an alert when current price <= target price.
- Designed for cron or Task Scheduler.

Notes & Tips
- Respect each site's robots.txt and Terms of Service.
- Keep intervals sane (e.g., 1–6 hours) and stagger checks.
- Many stores render prices via JS; prefer their public APIs or static pages.
- For Amazon, use Keepa/CamelCamelCamel rather than scraping (ToS + bot blocks).
"""

import sys
import time
import yaml
import sqlite3
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime, timezone
import re

DB_PATH = Path(__file__).with_name("price_history.db")
CONFIG_PATH = Path(__file__).with_name("products.yaml")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
}

def parse_price(text: str):
    """Extract a float from a price-ish string (handles $1,234.56 and 1.234,56)."""
    if text is None:
        return None
    s = text.strip()
    # Remove currency symbols and spaces
    s = re.sub(r"[^\d,.\s]", "", s).strip()
    s = s.replace(" ", "")

    # If both comma and dot exist, decide decimal by last occurrence
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            # Comma decimal -> remove thousand dots
            s = s.replace(".", "")
            s = s.replace(",", ".")
        else:
            # Dot decimal -> remove thousand commas
            s = s.replace(",", "")
    else:
        # Only one of comma or dot
        # If only comma, assume comma decimal (e.g., 1.234,56 or 123,45)
        if "," in s and "." not in s:
            # if there are multiple commas, keep last as decimal
            if s.count(",") > 1:
                parts = s.split(",")
                s = "".join(parts[:-1]) + "." + parts[-1]
            else:
                s = s.replace(",", ".")
        # If only dot, assume dot decimal; strip thousand separators heuristically
        if "." in s:
            # If more than one dot, remove all but the last
            if s.count(".") > 1:
                parts = s.split(".")
                s = "".join(parts[:-1]) + "." + parts[-1]

    try:
        return float(s)
    except ValueError:
        return None

def ensure_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """CREATE TABLE IF NOT EXISTS price_history (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               timestamp TEXT NOT NULL,
               name TEXT,
               url TEXT NOT NULL,
               price REAL,
               target REAL,
               selector TEXT,
               status TEXT
           )"""
    )
    conn.commit()
    conn.close()

def record(name, url, price, target, selector, status):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO price_history (timestamp, name, url, price, target, selector, status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (datetime.now(timezone.utc).isoformat(), name, url, price, target, selector, status),
    )
    conn.commit()
    conn.close()

def fetch_price(url, selector):
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
    except requests.RequestException as e:
        return None, f"fetch_error: {e}"
    soup = BeautifulSoup(r.text, "html.parser")
    el = soup.select_one(selector)
    if not el:
        return None, "selector_not_found"
    price = parse_price(el.get_text(strip=True))
    if price is None:
        return None, "parse_failed"
    return price, "ok"

def run_once():
    ensure_db()
    if not CONFIG_PATH.exists():
        print(f"Config not found: {CONFIG_PATH}. Create products.yaml. See example in repo.", file=sys.stderr)
        sys.exit(1)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    products = cfg.get("products", [])
    if not products:
        print("No products in config.", file=sys.stderr)
        sys.exit(1)

    any_alerts = False
    for p in products:
        name = p.get("name") or p.get("url")
        url = p["url"]
        selector = p["selector"]
        target = p.get("target_price")
        price, status = fetch_price(url, selector)
        record(name, url, price, target, selector, status)

        if status != "ok":
            print(f"[{name}] ERROR: {status} ({url})")
            continue

        print(f"[{name}] current={price} target={target} ({url})")
        if target is not None and price is not None and price <= float(target):
            any_alerts = True
            print(f"  👉 ALERT: price {price} <= target {target}")

    if not any_alerts:
        print("No alerts this run.")

if __name__ == "__main__":
    run_once()
