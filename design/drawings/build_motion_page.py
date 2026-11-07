"""Builds priority-card-motion.html: the motion scene played live in the browser (no video encoder needed).

Run: uv run --project api python design/drawings/build_motion_page.py
"""
from pathlib import Path

HERE = Path(__file__).parent
SKILL = Path.home() / ".claude/skills/dimensional-drawing-motion/templates"
css = (SKILL / "base.css").read_text(encoding="utf-8")
scene = (HERE / "scene-priority.js").read_text(encoding="utf-8")
page = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Priority Card Motion</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Arimo:wght@400;700&display=swap">
<style>
:root{color-scheme:light;--paper:#ececec;--ink:#111;--ink2:#444}
html,body{margin:0;background:var(--paper);color:var(--ink);font-family:Arimo,Helvetica,Arial,sans-serif}
.wrap{max-width:1600px;margin:0 auto;padding:20px 16px 32px}
.frame{position:relative;width:100%;aspect-ratio:16/9;background:#fff;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.12)}
#stage{position:absolute;left:0;top:0;width:1920px;height:1080px;transform-origin:0 0;overflow:hidden;--sans:Arimo,Helvetica,Arial,sans-serif;background:#fff}
.bar{display:flex;align-items:center;gap:12px;margin-top:12px;font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--ink2)}
button{font:inherit;text-transform:uppercase;letter-spacing:.06em;background:#fff;color:var(--ink);border:1px solid var(--ink);border-radius:8px;min-height:40px;min-width:88px;cursor:pointer}
button:focus-visible,input:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
input[type=range]{flex:1;accent-color:#111}
.t{font-variant-numeric:tabular-nums;min-width:96px;text-align:right}
</style>
<style>__CSS__</style>
</head>
<body>
<div class="wrap">
  <div class="frame" id="frame"><div id="stage"></div></div>
  <div class="bar">
    <button id="play" type="button" aria-label="Pause">Pause</button>
    <input id="scrub" type="range" min="0" max="11.5" step="0.01" value="0" aria-label="Film position">
    <span class="t" id="time">0.00 / 11.50 s</span>
  </div>
</div>
<script>
var SCENES = {};
var stage = document.getElementById('stage');
var kit = (function () {
  const clamp01 = x => Math.max(0, Math.min(1, x)), seg = (t, a, b) => clamp01((t - a) / (b - a)), lerp = (a, b, p) => a + (b - a) * p;
  const eo = x => 1 - Math.pow(1 - x, 3), ei = x => x * x * x, eio = x => (x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);
  return { seg, lerp, eo, ei, eio, clamp01, stage, width: 1920, height: 1080,
    h: s => { const d = document.createElement('div'); d.innerHTML = s.trim(); return d.firstElementChild; },
    css: s => { const st = document.createElement('style'); st.textContent = s; stage.appendChild(st); },
    scene: (id, o) => { SCENES[id] = o; } };
})();
</script>
<script>__JS__</script>
<script>
(function () {
  const SC = SCENES.drawing, DUR = 11.5, frame = document.getElementById('frame');
  const play = document.getElementById('play'), scrub = document.getElementById('scrub'), time = document.getElementById('time');
  SC.init(kit);
  const fit = () => { stage.style.transform = 'scale(' + frame.clientWidth / 1920 + ')'; };
  new ResizeObserver(fit).observe(frame); fit();
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  let t = reduced ? DUR : 0, playing = !reduced, last = null;
  const show = () => { SC.render(t, kit); scrub.value = t; time.textContent = t.toFixed(2) + ' / ' + DUR.toFixed(2) + ' s';
    play.textContent = playing ? 'Pause' : 'Play'; play.setAttribute('aria-label', playing ? 'Pause' : 'Play'); };
  const tick = now => { if (playing) { if (last !== null) t += (now - last) / 1000; if (t >= DUR) { t = DUR; playing = false; } }
    last = now; show(); requestAnimationFrame(tick); };
  play.onclick = () => { if (t >= DUR) t = 0; playing = !playing; last = null; show(); };
  scrub.oninput = () => { t = +scrub.value; playing = false; show(); };
  document.addEventListener('keydown', e => { if (e.code === 'Space' && e.target === document.body) { e.preventDefault(); play.click(); } });
  requestAnimationFrame(tick);
})();
</script>
</body>
</html>
"""
(HERE / "priority-card-motion.html").write_text(page.replace("__CSS__", css).replace("__JS__", scene), encoding="utf-8")
print("wrote", HERE / "priority-card-motion.html")
