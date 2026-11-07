"""Builds <slug>.html (static sheet) and <slug>-motion.html (film) from <slug>.geometry.js.

Geometry holds the measured plan, dims and tables, using the drawing kit from scene-priority.js. An optional first
line `//CAM [...]` sets the camera keys. Needs Playwright (dev dependency) for the static sheet.
Run: uv run --project api python design/drawings/build_drawing.py step-item "STEP ITEM" "scope sentence" "source cell"
"""
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
SKILL = Path.home() / ".claude/skills/dimensional-drawing-motion/templates"
slug, title, scope, source = sys.argv[1:5]
css = (SKILL / "base.css").read_text(encoding="utf-8")
src = (HERE / "scene-priority.js").read_text(encoding="utf-8")
geom = (HERE / f"{slug}.geometry.js").read_text(encoding="utf-8")

DEFAULT_CAM = [{"t": 0, "cx": 520, "cy": 330, "z": 3.4}, {"t": 2.2, "cx": 530, "cy": 335, "z": 3.2},
               {"t": 4.0, "cx": 700, "cy": 470, "z": 1.55}, {"t": 5.4, "cx": 704, "cy": 472, "z": 1.52},
               {"t": 7.2, "cx": 1180, "cy": 450, "z": 1.5}, {"t": 8.0, "cx": 1184, "cy": 452, "z": 1.48},
               {"t": 9.4, "cx": 930, "cy": 530, "z": 1.0}, {"t": 13, "cx": 930, "cy": 530, "z": 0.99}]
m = re.match(r"//CAM (\[.*\])\n", geom)
cam = json.loads(m.group(1)) if m else DEFAULT_CAM
cam_js = "const DW_CAM = " + json.dumps(cam) + ";"
head = re.sub(r"const DW_CAM = \[.*?\];", lambda _: cam_js, src.split("    /* Measured geometry")[0], count=1, flags=re.S)
tail = "  },\n  render(t) {" + src.split("  },\n  render(t) {", 1)[1]
scene = head + geom + tail
(HERE / f"scene-{slug}.js").write_text(scene, encoding="utf-8")

shell = (HERE / "build_motion_page.py").read_text(encoding="utf-8").split('page = """', 1)[1].split('"""\n(HERE', 1)[0]
shell = shell.replace("Priority Card Motion", f"{title.title()} Motion")
film = HERE / f"{slug}-motion.html"
film.write_text(shell.replace("__CSS__", css).replace("__JS__", scene), encoding="utf-8")

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1920, "height": 1080})
    pg.goto(film.as_uri())
    pg.wait_for_timeout(500)
    pg.evaluate("()=>{const s=document.getElementById('scrub');s.value=11.5;s.dispatchEvent(new Event('input'))}")
    pg.wait_for_timeout(300)
    svg = pg.evaluate("()=>document.querySelector('.dw-svg').cloneNode(true).outerHTML")
    sty = pg.evaluate("()=>[...document.querySelectorAll('#stage style')].map(s=>s.textContent).join(' ')")
    b.close()

cells = [("DWG NO.", f"UI-{slug.upper()}-001"), ("REV", "A · 2026-11-06"), ("SHEETS", "1"), ("UNITS", "CSS PX @ 1×"),
         ("SCALE", "NOTED PER VIEW"), ("SOURCE", source)]
tb = "".join(f'<div class="c"><small>{a}</small>{v}</div>' for a, v in cells)
html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<style>{css}
html,body{{margin:0;background:#ececec;color:#111;font-family:Arimo,Helvetica,Arial,sans-serif;color-scheme:light}}
.wrap{{max-width:1600px;margin:0 auto;padding:16px}}
.tb{{border:1.2px solid #111;border-radius:16px;background:#fff;display:grid;grid-template-columns:2fr repeat(3,1fr);margin-bottom:16px;overflow:hidden}}
.tb .t{{grid-row:span 2;padding:16px;border-right:.8px solid #111}} .tb h1{{margin:6px 0;font-weight:300;letter-spacing:.14em;font-size:40px}}
.tb .c{{padding:10px 14px;border-bottom:.8px solid #111;border-right:.8px solid #111;font-size:13px;text-transform:uppercase}} small{{display:block;font-size:9.5px;letter-spacing:.08em;color:#444}}
.sheet{{background:#fff;overflow-x:auto;position:relative}} .sheet svg.dw-svg{{position:static;width:100%;min-width:1100px;height:auto;display:block}}
.foot{{display:flex;justify-content:space-between;font-size:11px;letter-spacing:.06em;text-transform:uppercase;margin-top:8px;color:#444}}
{sty}
</style></head><body><div class="wrap">
<div class="tb"><div class="t"><small>UI COMPONENT · DIMENSIONAL DRAWING</small><h1>{title}</h1><small>{scope}</small></div>{tb}</div>
<div class="sheet" id="stage">{svg}</div>
<div class="foot"><span>2026-11-06 | UI component reference</span><span>{title.title()}, architecture | 1</span></div></div></body></html>"""
(HERE / f"{slug}.html").write_text(html, encoding="utf-8")
print("wrote", slug)
