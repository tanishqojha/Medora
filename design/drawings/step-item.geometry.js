    /* Measured at 1440 px on /welcome: step item 259 wide. Row = 1096 = 1152 - 2*28. */
    const W = 259, H = 201, k = 2, PX = 470, PY = 300, X = v => PX + v * k, Y = v => PY + v * k;
    const r = (x, y, w, h, rx, c, l, al) => { rr(X(x), Y(y), w * k, h * k, rx * k, c); if (l) slotLabel(X(x), Y(y), w * k, h * k, l, al); };
    this.morph = []; this.iso = [1, 0, 0, 1, 0, 0]; this.flat = this.iso;

    at(-0.9, 0, 1.8); mk('line', { x1: X(0), y1: Y(0), x2: X(W), y2: Y(0), class: 'obj' });
    at(0.3, 0, .6); r(0, 0, W, H, 0, 'ph');
    at(0.6, .25, .6); r(0, 17, 60, 44, 2, 'slot', 'Numeral · hug', 'l'); r(0, 69, W, 24, 2, 'slot', 'Title slot · fill', 'l'); r(0, 101, W, 100, 2, 'slot', 'Body slot · hug · max 34ch', 'l');
    at(1.4, .1, .45); dimV(Y(0), Y(1), X(-30), X(0), X(0), 'B', { side: 'l', dy: -10 }); dimV(Y(1), Y(17), X(-30), X(0), X(0), 'S1', { side: 'l', dy: -4 }); dimV(Y(17), Y(61), X(-30), X(0), X(0), 'H1', { side: 'l' });
    at(2.0, .08, .45); dimV(Y(61), Y(69), X(-30), X(0), X(0), 'S2', { side: 'l', dy: -8 }); dimV(Y(69), Y(93), X(-30), X(0), X(0), 'H2', { side: 'l' }); dimV(Y(93), Y(101), X(-30), X(0), X(0), 'S2', { side: 'l', dy: 8 }); dimV(Y(101), Y(H), X(-30), X(0), X(0), 'HUG', { side: 'l', c: 'dts' });
    at(3.2, .1, .5); mk('line', { x1: X(-14), y1: Y(39), x2: X(W + 14), y2: Y(39), class: 'cl' }); dimH(X(0), X(W), Y(-30), Y(0), Y(0), 'W'); tx(X(W / 2) + 40, Y(-30) - 4, '= (ROW − 3·G) ÷ 4 · fill', 'dts');
    at(3.5, .1, .5); dimV(Y(0), Y(H), X(-76), X(0), X(0), 'H = B + S1 + H1 + 2·S2 + H2 + HUG', { c: 'dts' });
    at(3.9, .05, .4); nb(X(W) + 20, Y(0), 1); nb(X(W) + 20, Y(50), 2); nb(X(W) + 20, Y(150), 3); callout(X(150), Y(150), X(W) + 40, Y(185), 'MAX 34CH', 1, 'dts');
    at(4.2, .1, .5); title(X(W / 2), Y(H) + 50, 'Plan view', 'Scale 2:1 · step item · synthetic page');

    /* strip: four items, one grid row */
    { const s = .4, SX = 1075, SY = 330, sx = v => SX + v * s, sy = v => SY + v * s, G = 20, RW = 4 * W + 3 * G;
      at(5.6, .08, .5); for (let i = 0; i < 4; i++) { const x = i * (W + G); mk('line', { x1: sx(x), y1: sy(0), x2: sx(x + W), y2: sy(0), class: 'obj' }); rr(sx(x), sy(17), 60 * s, 44 * s, 1, 'slot'); rr(sx(x), sy(69), W * s, 24 * s, 1, 'slot'); rr(sx(x), sy(101), W * s, 100 * s, 1, 'slot'); }
      at(6.4, .06, .45); dimH(sx(0), sx(W), sy(-24), sy(0), sy(0), 'W'); dimH(sx(W), sx(W + G), sy(-24), sy(0), sy(0), 'G', { dx: 2 }); dimH(sx(0), sx(RW), sy(-56), sy(-24), sy(-24), 'ROW = 4·W + 3·G = 1096');
      dimV(sy(0), sy(H), sx(RW) + 24, sx(RW), sx(RW), 'H (REF)', { side: 'r' }); nb(sx(RW) + 8, sy(-24), 4);
      title(sx(RW / 2), sy(H) + 40, 'Row of four', 'Scale 0.4:1 · one grid row at 1440 px'); }

    /* the rest of the sheet */
    at(7.4, 0, 1.6); rr(20, 20, 1860, 1020, 16, 'border');
    at(8.2, .05, .4); notes([[1, 'Top rule only, 1 px. No card, no fill, no icon.'], [2, 'Numeral is decorative (aria-hidden). Title is the heading.'], [3, 'Body text is capped at 34ch. HUG height.'], [4, 'Row height is stretched to the tallest item. H is the hug height.'], [0, 'All dimensions CSS px at 1440. Slots are placeholders. Values are measured, not designed.']]);
    at(8.5, .006, .25); let yy = table(1620, 86, 'Spacing', [['B', 'rule-w', '1'], ['S1', 'pad-top', '16'], ['S2', 'stack-gap', '8'], ['G', 'col-gap', '20']]);
    yy = table(1620, yy, 'Size', [['H1', 'numeral-h', '36 / lh 44'], ['H2', 'title-h', '18 / lh 24'], ['HUG', 'body-h', 'REF 100'], ['H', 'item-h', 'REF 201'], ['W', 'item-w', '259']]);
    table(1620, yy, 'Type', [['T1', 'numeral', '36 · 700'], ['T2', 'title', '18 · 600'], ['T3', 'body', '14 / 20'], ['MW', 'body-max', '34ch']]);
