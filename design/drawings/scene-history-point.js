const { seg, lerp, eo, eio, clamp01 } = kit;
const DW_NS = 'http://www.w3.org/2000/svg';
/* Camera: close on the chips/title corner -> plan -> exploded view -> whole sheet. Scene seconds (scaled by 0.85). */
const DW_CAM = [{"t": 0, "cx": 480, "cy": 285, "z": 3.4}, {"t": 2.2, "cx": 490, "cy": 290, "z": 3.2}, {"t": 4.0, "cx": 810, "cy": 370, "z": 1.5}, {"t": 5.4, "cx": 814, "cy": 372, "z": 1.48}, {"t": 7.0, "cx": 640, "cy": 690, "z": 1.35}, {"t": 7.8, "cx": 644, "cy": 692, "z": 1.33}, {"t": 9.4, "cx": 950, "cy": 530, "z": 1.0}, {"t": 13, "cx": 950, "cy": 530, "z": 0.99}];
kit.scene('drawing', {
  init(kit) {
    kit.css('.dw-svg .dt{font-size:11px;fill:var(--main);paint-order:stroke;stroke:var(--ground);stroke-width:4px;stroke-linejoin:round}' +
      '.dw-svg .dts{font-size:9.5px;fill:color-mix(in srgb,var(--second) 75%,var(--ground));letter-spacing:.06em;paint-order:stroke;stroke:var(--ground);stroke-width:3px}' +
      '.dw-svg .sl{font-size:9px;fill:color-mix(in srgb,var(--second) 75%,var(--ground));letter-spacing:.08em}' +
      '.dw-svg .nt{font-size:11.5px;fill:var(--main);letter-spacing:.06em}.dw-svg .nth{font-size:13px;font-weight:700;fill:var(--main);letter-spacing:.06em}' +
      '.dw-svg .vt{font-size:12px;fill:var(--main);letter-spacing:.1em}.dw-svg .nbt{font-size:9.5px;fill:var(--main)}' +
      '.dw-svg .th{font-size:10.5px;fill:var(--main);letter-spacing:.05em}.dw-svg .tc{font-size:10.5px;fill:var(--main);text-transform:none}');
    const root = kit.h('<div class="ground"><div class="dw-cam"></div></div>');
    kit.stage.append(root);
    const camEl = root.querySelector('.dw-cam');
    this.cam = camEl.style;
    const svg = document.createElementNS(DW_NS, 'svg');
    svg.setAttribute('viewBox', '0 0 1900 1060'); svg.setAttribute('width', '1900'); svg.setAttribute('height', '1060'); svg.setAttribute('class', 'dw-svg');
    camEl.appendChild(svg);
    const REG = this.reg = []; let sv = svg, CUR = { a: 0, s: 0, d: .6, i: 0 }, noreg = 0;
    const at = (a, s, d) => { CUR = { a: a, s: s || 0, d: d || .6, i: 0 }; };
    const kind = (e, t) => { if (t === 'text') return 'f'; const c = ' ' + (e.getAttribute('class') || '') + ' ';
      if (/ (slot|ph|cl|env|hs) /.test(c) || (e.getAttribute('fill') || '').indexOf('url') === 0) return 'f'; return 'd'; };
    function mk(t, a, p) { const e = document.createElementNS(DW_NS, t); for (const k in a) if (a[k] != null) e.setAttribute(k, a[k]); (p || sv).appendChild(e);
      if (!noreg && t !== 'g') { const s = CUR.a + CUR.i * CUR.s; CUR.i++; const k = kind(e, t); if (k === 'd') e.setAttribute('pathLength', '1'); e.style.opacity = 0; REG.push({ e: e, a: s, b: s + CUR.d, k: k, last: -1 }); }
      return e; }
    function tx(x, y, s, c, a, p) { const t = mk('text', Object.assign({ x: x, y: y, class: c || 'dt' }, a || {}), p); t.textContent = s; return t; }
    noreg = 1; const d = mk('defs', {}); const m = mk('marker', { id: 'dwar', viewBox: '0 0 10 10', refX: 10, refY: 5, markerWidth: 7, markerHeight: 7, orient: 'auto-start-reverse', markerUnits: 'userSpaceOnUse' }, d);
    mk('path', { d: 'M0,1.7 L10,5 L0,8.3 z', class: 'arrow' }, m);
    const pt = mk('pattern', { id: 'dwhat', width: 5, height: 5, patternUnits: 'userSpaceOnUse', patternTransform: 'rotate(45)' }, d); mk('line', { x1: 0, y1: 0, x2: 0, y2: 5, class: 'hl' }, pt); noreg = 0;
    const A = 'url(#dwar)', HAT = 'url(#dwhat)';
    function dimH(x1, x2, y, e1, e2, l, o) { o = o || {}; [[x1, e1], [x2, e2]].forEach(([x, e]) => { if (e == null) return; const s = Math.sign(y - e) || 1; mk('line', { x1: x, y1: e + s * 3, x2: x, y2: y + s * 5, class: 'ext' }); });
      if (x2 - x1 >= 28) mk('line', { x1: x1, y1: y, x2: x2, y2: y, class: 'dl', 'marker-start': A, 'marker-end': A }); else { mk('line', { x1: x1 - 13, y1: y, x2: x1, y2: y, class: 'dl', 'marker-end': A }); mk('line', { x1: x2 + 13, y1: y, x2: x2, y2: y, class: 'dl', 'marker-end': A }); }
      tx((x1 + x2) / 2 + (o.dx || 0), (o.below ? y + 13 : y - 4) + (o.dy || 0), l, o.c || 'dt', { 'text-anchor': o.anchor || 'middle' }); }
    function dimV(y1, y2, x, e1, e2, l, o) { o = o || {}; [[y1, e1], [y2, e2]].forEach(([y, e]) => { if (e == null) return; const s = Math.sign(x - e) || 1; mk('line', { x1: e + s * 3, y1: y, x2: x + s * 5, y2: y, class: 'ext' }); });
      if (y2 - y1 >= 28) mk('line', { x1: x, y1: y1, x2: x, y2: y2, class: 'dl', 'marker-start': A, 'marker-end': A }); else { mk('line', { x1: x, y1: y1 - 13, x2: x, y2: y1, class: 'dl', 'marker-end': A }); mk('line', { x1: x, y1: y2 + 13, x2: x, y2: y2, class: 'dl', 'marker-end': A }); }
      const c = (y1 + y2) / 2 + (o.dy || 0); if (o.side) { const r = o.side === 'r'; tx(r ? x + 6 : x - 6, c + 4, l, o.c || 'dt', { 'text-anchor': r ? 'start' : 'end' }); } else tx(x - 5, c, l, o.c || 'dt', { 'text-anchor': 'middle', transform: 'rotate(-90 ' + (x - 5) + ' ' + c + ')' }); }
    function callout(px, py, ex, ey, l, dir, c) { const s = dir || (ex >= px ? 1 : -1); mk('circle', { cx: px, cy: py, r: 1.8, class: 'dot' }); mk('polyline', { points: px + ',' + py + ' ' + ex + ',' + ey + ' ' + (ex + s * 10) + ',' + ey, class: 'lead' }); tx(ex + s * 14, ey + 4, l, c || 'dt', { 'text-anchor': s > 0 ? 'start' : 'end' }); }
    function rad(cx, cy, r, c, l, L) { const sx = c.indexOf('l') > -1 ? -1 : 1, sy = c.indexOf('t') > -1 ? -1 : 1; const ox = cx - sx * r, oy = cy - sy * r; callout(ox + sx * r * Math.SQRT1_2, oy + sy * r * Math.SQRT1_2, ox + sx * r * Math.SQRT1_2 + sx * L, oy + sy * r * Math.SQRT1_2 + sy * L, l, sx); }
    function nb(x, y, n) { mk('rect', { x: x - 6, y: y - 6, width: 12, height: 12, class: 'nb' }); tx(x, y + 3.5, String(n), 'nbt', { 'text-anchor': 'middle' }); }
    function rr(x, y, w, h, r, c, p) { return mk('rect', { x: x, y: y, width: w, height: h, rx: r, class: c }, p); }
    function slotLabel(x, y, w, h, l, al, p) { tx(al === 'l' ? x + 6 : x + w / 2, y + h / 2 + 3.2, l, 'sl', { 'text-anchor': al === 'l' ? 'start' : 'middle' }, p); }
    function title(x, y, t, s) { tx(x, y, t, 'vt', { 'text-anchor': 'middle' }); if (s) tx(x, y + 14, s, 'dts', { 'text-anchor': 'middle' }); }
    function xbox(x, y, w, h, p) { mk('rect', { x: x, y: y, width: w, height: h, class: 'thin' }, p); mk('path', { d: 'M' + x + ',' + y + ' l' + w + ',' + h + ' M' + (x + w) + ',' + y + ' l' + (-w) + ',' + h, class: 'thin' }, p); }
    function detailRef(cx, cy, r, lbl, lx, ly) { mk('circle', { cx: cx, cy: cy, r: r, class: 'ph' }); const a = Math.atan2(ly - cy, lx - cx); mk('line', { x1: cx + r * Math.cos(a), y1: cy + r * Math.sin(a), x2: lx, y2: ly, class: 'lead' }); tx(lx + (lx < cx ? -4 : 4), ly + 4, lbl, 'dts', { 'text-anchor': lx < cx ? 'end' : 'start' }); }
    function table(x, y, ttl, rows) { const ws = [40, 88, 96], rh = 17; tx(x, y - 8, ttl, 'vt'); [['Code', 'Variable', 'Value']].concat(rows).forEach((r, i) => { let c2 = x; r.forEach((c, j) => { mk('rect', { x: c2, y: y + i * rh, width: ws[j], height: rh, class: 'thin' }); tx(c2 + (j ? ws[j] / 2 : 6), y + i * rh + 12, c, i ? 'tc' : 'th', { 'text-anchor': j ? 'middle' : 'start' }); c2 += ws[j]; }); }); return y + (rows.length + 1) * rh + 34; }
    function notes(list) { tx(50, 58, 'Notes:', 'nth'); tx(112, 58, '(unless otherwise specified)', 'nt'); list.forEach(([n, t], i) => { const y = 88 + i * 24; if (n) { nb(56, y - 4, n); tx(72, y, t, 'nt'); } else tx(50, y, t, 'nt'); }); }

//CAM [{"t":0,"cx":480,"cy":285,"z":3.4},{"t":2.2,"cx":490,"cy":290,"z":3.2},{"t":4.0,"cx":810,"cy":370,"z":1.5},{"t":5.4,"cx":814,"cy":372,"z":1.48},{"t":7.0,"cx":640,"cy":690,"z":1.35},{"t":7.8,"cx":644,"cy":692,"z":1.33},{"t":9.4,"cx":950,"cy":530,"z":1.0},{"t":13,"cx":950,"cy":530,"z":0.99}]
    /* Measured at 1440 px on /doctor: history point row, 640 wide, 88 high with a detail line. */
    const W = 640, H = 88, k = 1.5, PX = 330, PY = 250, X = v => PX + v * k, Y = v => PY + v * k;
    const r = (x, y, w, h, rx, c, l, al) => { rr(X(x), Y(y), w * k, h * k, rx * k, c); if (l) slotLabel(X(x), Y(y), w * k, h * k, l, al); };
    this.morph = []; this.iso = [1, 0, 0, 1, 0, 0]; this.flat = this.iso;

    /* plan: rail line first, then dot, then the slots */
    at(-0.9, 0, 1.8); mk('line', { x1: X(108), y1: Y(0), x2: X(108), y2: Y(H), class: 'obj' });
    at(0.4, 0, .9); mk('circle', { cx: X(108), cy: Y(24), r: 6 * k, class: 'obj' }); mk('circle', { cx: X(108), cy: Y(24), r: 10 * k, class: 'ph' });
    at(0.9, 0, .6); r(0, 0, W, H, 0, 'ph');
    at(1.2, .22, .6); r(0, 8, 88, 24, 2, 'slot', 'Date slot · right', 'l'); r(128, 8, 512, 24, 2, 'slot', 'Label slot · fill', 'l'); r(128, 32, 512, 20, 2, 'slot', 'Detail slot · optional · fill', 'l');
    at(2.4, .15, .55); r(128, 56, 120, 16, 8, 'hug', 'Gap chip · hug', 'c'); r(256, 56, 190, 16, 2, 'slot', 'Source slot · hug', 'l');
    at(3.1, .08, .45); dimV(Y(0), Y(8), X(-30), X(0), X(0), 'S1', { side: 'l', dy: -8 }); dimV(Y(8), Y(32), X(-30), X(0), X(0), 'H1', { side: 'l' }); dimV(Y(32), Y(52), X(-30), X(0), X(0), 'H2', { side: 'l' });
    at(3.5, .08, .45); dimV(Y(52), Y(56), X(-30), X(0), X(0), 'S2', { side: 'l', dy: -6 }); dimV(Y(56), Y(72), X(-30), X(0), X(0), 'H3', { side: 'l' }); dimV(Y(72), Y(88), X(-30), X(0), X(0), 'S3', { side: 'l', dy: 6 });
    at(3.9, .1, .5); dimV(Y(0), Y(H), X(-76), X(0), X(0), 'H = S1 + H1 + H2 + S2 + H3 + S3 = REF 88', { c: 'dts' });
    at(4.2, .08, .45); dimH(X(0), X(96), Y(-24), Y(0), Y(0), 'W1'); dimH(X(96), X(120), Y(-24), Y(0), Y(0), 'W2', { dy: -10 }); dimH(X(120), X(W), Y(-24), Y(0), Y(0), 'FILL', { c: 'dts' });
    at(4.5, .06, .4); mk('line', { x1: X(108), y1: Y(-8), x2: X(108), y2: Y(H + 8), class: 'cl' }); nb(X(108), Y(H) + 18, 1); nb(X(108) - 21, Y(24), 2); nb(X(84), Y(14), 3); nb(X(W) + 18, Y(42), 4);
    at(4.8, .1, .5); title(X(W / 2), Y(H) + 52, 'Plan view', 'Scale 1.5:1 · history point with detail line');

    /* detail A: dot and rail at 5:1 */
    { const s = 5, CX = 430, T = 540, dy = v => T + v * s;
      at(5.6, .08, .5); mk('rect', { x: CX - 12 * s, y: dy(0), width: 24 * s, height: 60 * s, class: 'ph' }); mk('rect', { x: CX - 1 * s, y: dy(0), width: 2 * s, height: 60 * s, class: 'hug' });
      mk('circle', { cx: CX, cy: dy(24), r: 10 * s, class: 'ph' }); mk('circle', { cx: CX, cy: dy(24), r: 6 * s, class: 'obj' });
      at(6.2, .06, .4); dimV(dy(0), dy(18), CX - 12 * s - 24, CX - 12 * s, CX - 12 * s, 'D1', { side: 'l' }); dimV(dy(18), dy(30), CX - 12 * s - 24, CX - 12 * s, CX - 12 * s, 'Z1', { side: 'l' });
      dimH(CX - 12 * s, CX + 12 * s, dy(-3), dy(0), dy(0), 'W2'); dimH(CX - 1 * s, CX + 1 * s, dy(64), dy(60), dy(60), 'B', { below: true });
      callout(CX + 8 * s * Math.SQRT1_2, dy(24) - 8 * s * Math.SQRT1_2, CX + 12 * s + 50, dy(10), 'RG = 4 · PAGE GROUND', 1, 'dts');
      title(CX, dy(60) + 56, 'Detail A · dot and rail', 'Scale 5:1 · Z2 = Z1 + 2·RG = 20'); }

    /* detail B: last row, rail stops at L1 */
    { const s = .9, BX = 820, BY = 610, bx = v => BX + v * s, by = v => BY + v * s;
      at(6.8, .08, .5); mk('rect', { x: bx(0), y: by(0), width: W * s, height: H * s, class: 'ph' }); mk('line', { x1: bx(108), y1: by(0), x2: bx(108), y2: by(20), class: 'obj' }); mk('circle', { cx: bx(108), cy: by(24), r: 6 * s, class: 'obj' });
      rr(bx(128), by(8), 512 * s, 24 * s, 2, 'slot'); rr(bx(128), by(56), 120 * s, 16 * s, 8 * s, 'hug');
      at(7.2, .06, .4); dimV(by(0), by(20), bx(-26), bx(0), bx(0), 'L1', { side: 'l' }); nb(bx(W) + 16, by(10), 1);
      title(bx(W / 2), by(H) + 44, 'Detail B · last row', 'Scale 0.9:1 · rail ends at L1'); }

    /* the rest of the sheet */
    at(7.4, 0, 1.6); rr(20, 20, 1860, 1020, 16, 'border');
    at(8.2, .05, .4); notes([[1, 'Rail line B runs the full row height. On the last row it stops at L1.'], [2, 'Dot is centered on the rail, D1 below the row top. Ring is page ground, RG.'], [3, 'Date is right aligned in W1 with tabular figures. No time of day.'], [4, 'Detail slot is optional. H = REF 88 includes it. Without it H = 68.'], [0, 'All dimensions CSS px at 1440. Slots are placeholders. Values are measured, not designed.']]);
    at(8.5, .006, .25); let yy = table(1620, 86, 'Spacing', [['S1', 'body-pad-t', '8'], ['S2', 'meta-gap', '4'], ['S3', 'body-pad-b', '16'], ['S4', 'date-pad-r', '8']]);
    yy = table(1620, yy, 'Size', [['H1', 'label-h', '18 / lh 24'], ['H2', 'detail-h', '14 / lh 20'], ['H3', 'meta-h', '16'], ['H', 'row-h', 'REF 88']]);
    yy = table(1620, yy, 'Width', [['W1', 'date-col', '96'], ['W2', 'rail-col', '24'], ['FILL', 'body-col', 'rest']]);
    table(1620, yy, 'Rail and dot', [['B', 'rail-w', '2'], ['Z1', 'dot', '12'], ['RG', 'ring', '4'], ['D1', 'dot-top', '18'], ['L1', 'last-rail', '20']]);
  },
  render(t) {
    t = t / 0.85;
    let i = 0; while (i < DW_CAM.length - 2 && t > DW_CAM[i + 1].t) i++;
    const c0 = DW_CAM[i], c1 = DW_CAM[i + 1], p = eio(seg(t, c0.t, c1.t));
    const z = Math.exp(lerp(Math.log(c0.z), Math.log(c1.z), p)), cx = lerp(c0.cx, c1.cx, p), cy = lerp(c0.cy, c1.cy, p);
    this.cam.transform = 'translate(' + (960 - cx * z) + 'px,' + (540 - cy * z) + 'px) scale(' + z + ')';
    for (const it of this.reg) {
      let v = clamp01((t - it.a) / (it.b - it.a)); v = Math.round(v * 400) / 400;
      if (v === it.last) continue; it.last = v; const s = it.e.style;
      if (it.k === 'f') { s.opacity = eo(v); continue; }
      const e = eio(v); s.opacity = Math.min(1, v * 6);
      if (v >= 1) { s.strokeDasharray = ''; s.strokeDashoffset = ''; } else { s.strokeDasharray = '1 2'; s.strokeDashoffset = 1 - e; }
      s.fillOpacity = eo(seg(v, .55, 1));
    }
    const F = this.flat, I = this.iso;
    this.morph.forEach((m) => {
      const v = eio(seg(t, m.a, m.a + 1.5)), M = F.map((f, n) => lerp(f, I[n], v));
      M[5] -= m.z * v;
      m.g.style.opacity = eo(seg(t, m.a + 0.05, m.a + 0.5));
      const fo = eo(seg(t, m.a + 0.55, m.a + 1.25)); if (fo !== m.fo) { m.fo = fo; m.fills = m.fills || m.g.querySelectorAll('.obj,.well,.hug'); m.fills.forEach(e => { e.style.fillOpacity = fo; }); }
      m.g.setAttribute('transform', 'matrix(' + M.join(',') + ')');
      m.g.style.setProperty('--u', 1 / Math.sqrt(Math.abs(M[0] * M[3] - M[1] * M[2])));
    });
  },
});
