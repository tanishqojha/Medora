"""S18 step 8: screenshot every built screen for comparison with design/stitch/*.png.

Needs the stack running (scripts/dev.sh) with a demo tenant. Writes design/built/<screen>.png.
Usage: uv run --project api python scripts/screenshots.py [--base http://localhost:3000]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "design" / "built"
PASSWORD = "medora-demo"


def login(page: Page, base: str, email: str) -> None:
    page.goto(f"{base}/login")
    page.fill('input[type="email"]', email)
    page.fill('input[type="password"]', PASSWORD)
    page.click('button[type="submit"]')
    page.wait_for_url(lambda u: "/login" not in u, timeout=15000)


def api(page: Page, path: str):
    return page.evaluate("p => fetch('/api' + p, {credentials: 'include'}).then(r => r.json())", path)


def shot(page: Page, base: str, path: str, name: str) -> None:
    page.goto(f"{base}{path}")
    page.wait_for_load_state("networkidle")
    time.sleep(0.8)
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
    print("saved", name)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:3000")
    base = ap.parse_args().base
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        desk = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        page = desk.new_page()
        shot(page, base, "/login", "login")

        login(page, base, "steward@medora.test")
        new_shape = ROOT / "data" / "demo" / "opd_list_new_shape.csv"
        jobs = api(page, "/jobs")
        if new_shape.exists() and not any(j["filename"] == new_shape.name for j in jobs):
            page.goto(f"{base}/uploads")
            page.set_input_files('input[type="file"]', str(new_shape))
            for _ in range(30):
                time.sleep(1)
                if any(j["state"] == "needs_mapping" for j in api(page, "/jobs")):
                    break
            jobs = api(page, "/jobs")
        shot(page, base, "/uploads", "uploads")
        waiting = next((j for j in jobs if j["state"] == "needs_mapping"), None)
        if waiting:
            shot(page, base, f"/uploads/{waiting['id']}/mapping", "mapping")
        shot(page, base, "/review", "review")

        login(page, base, "meera@medora.test")
        shot(page, base, "/", "stuck")
        stuck = api(page, "/stuck")["items"]
        if stuck:
            shot(page, base, f"/patients/{stuck[0]['patient_id']}?flag={stuck[0]['id']}", "timeline")
            phone = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True)
            mp = phone.new_page()
            login(mp, base, "meera@medora.test")
            shot(mp, base, f"/call/{stuck[0]['id']}", "callcard")
            phone.close()

        login(page, base, "lead@medora.test")
        shot(page, base, "/pathways", "pathway")
        shot(page, base, "/nurse", "nurse")
        login(page, base, "admin@medora.test")
        shot(page, base, "/trust", "trust")
        shot(page, base, "/audit", "audit")
        browser.close()
    print(json.dumps(sorted(x.name for x in OUT.iterdir())))
    return 0


if __name__ == "__main__":
    urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=5)
    sys.exit(main())
