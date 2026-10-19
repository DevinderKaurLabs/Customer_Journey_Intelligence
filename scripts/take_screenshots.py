"""Screenshot every page of the app, plus one focused shot per use case.

    pip install playwright && python -m playwright install chromium
    python scripts/take_screenshots.py            # writes outputs/screenshots/*.png

Run it after scripts/run_pipeline.py, so the shots show your current data
(demo or the real REES46 files). Customers are picked from outputs/showcase.json.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "screenshots"
PORT = 8599
BASE = f"http://localhost:{PORT}"
HIDE_CHROME = """
header[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stStatusWidget"], footer {display:none !important}
.block-container {padding-top: 1.2rem !important}
"""


def wait_for_server(timeout: int = 90) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            urllib.request.urlopen(BASE + "/_stcore/health", timeout=2)
            return
        except Exception:
            time.sleep(1)
    raise RuntimeError("Streamlit did not start")


def settle(page, extra: float = 2.5) -> None:
    page.wait_for_selector('[data-testid="stAppViewContainer"]', timeout=60000)
    # wait until Streamlit stops running the script
    for _ in range(120):
        if page.locator('[data-testid="stStatusWidget"]').count() == 0 or \
           "Running" not in (page.locator('[data-testid="stStatusWidget"]').inner_text() or ""):
            break
        time.sleep(0.5)
    time.sleep(extra)  # plotly animations
    page.add_style_tag(content=HIDE_CHROME)
    time.sleep(0.3)


def full(page, name: str) -> None:
    h = page.evaluate(
        "() => { const m = document.querySelector('[data-testid=\"stMain\"]') || document.querySelector('section.main');"
        " return m ? m.scrollHeight : document.body.scrollHeight }"
    )
    page.set_viewport_size({"width": 1440, "height": max(900, int(h) + 20)})
    time.sleep(1.2)
    page.screenshot(path=str(OUT / name), full_page=True)
    page.set_viewport_size({"width": 1440, "height": 900})


def block(page, heading: str, name: str) -> None:
    """Screenshot the row of columns that holds a subheader."""
    loc = page.locator(
        f'xpath=//*[self::h2 or self::h3][contains(normalize-space(.), "{heading}")]'
        '/ancestor::div[@data-testid="stHorizontalBlock"][1]'
    ).first
    if loc.count() == 0:
        loc = page.locator(f'xpath=//*[self::h2 or self::h3][contains(normalize-space(.), "{heading}")]/ancestor::div[@data-testid="stVerticalBlock"][1]').first
    box = loc.bounding_box() or {"height": 800}
    page.set_viewport_size({"width": 1440, "height": int(box["height"]) + 240})
    time.sleep(0.8)
    loc.scroll_into_view_if_needed()
    time.sleep(0.6)
    loc.screenshot(path=str(OUT / name))
    page.set_viewport_size({"width": 1440, "height": 900})


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    show = json.loads((ROOT / "outputs" / "showcase.json").read_text())
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    server = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(ROOT / "app" / "Home.py"), "--server.port", str(PORT),
         "--server.headless", "true", "--browser.gatherUsageStats", "false"],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        wait_for_server()
        with sync_playwright() as p:
            exe = os.environ.get("CHROMIUM_PATH")
            browser = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=2)

            shots = [
                ("", "01_home.png", None),
                ("Journey_Map?mission=new_home", "02_journey_map.png", None),
                (f"Customer_Lens?customer={show['life_events']['new_home']['user_id']}", "03_use1_life_event.png", "The journey so far"),
                (f"Customer_Lens?customer={show['stages']['Researching']['user_id']}", "04_use2_stage.png", "What we think is going on"),
                (f"Customer_Lens?customer={show['next_need']['user_id']}", "05_use3_next_need.png", "Show next"),
                (f"Customer_Lens?customer={show['stop']['user_id']}", "06_use4_what_to_stop.png", "Stop showing"),
                ("Next_Need_Model", "07_next_need_model.png", None),
                ("Audiences", "08_audiences.png", None),
            ]
            for path, name, focus in shots:
                page.goto(f"{BASE}/{path}")
                settle(page)
                full(page, name.replace(".png", "_full.png") if focus else name)
                if focus:
                    page.goto(f"{BASE}/{path}")
                    settle(page)
                    if focus == "The journey so far":
                        loc = page.locator('[data-testid="stPlotlyChart"]').first
                        loc.scroll_into_view_if_needed()
                        time.sleep(0.8)
                        loc.screenshot(path=str(OUT / name))
                    else:
                        block(page, focus, name)
                print("saved", name)
            browser.close()
    finally:
        server.terminate()


if __name__ == "__main__":
    main()
