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
