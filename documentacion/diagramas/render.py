import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch()
    for nombre in sys.argv[1:]:
        src = Path(nombre).resolve()
        pg = b.new_page(viewport={"width": 720, "height": 600}, device_scale_factor=3)
        pg.goto(src.as_uri())
        pg.wait_for_timeout(300)
        h = pg.evaluate("document.body.scrollHeight")
        pg.set_viewport_size({"width": 720, "height": h})
        out = src.with_suffix(".png")
        pg.screenshot(path=str(out), full_page=True)
        print(out.name, h)
    b.close()
