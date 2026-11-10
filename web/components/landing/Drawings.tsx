/* Dimensional-drawing style SVGs for the landing page. Monochrome line work, codes and leaders, no real data.
   Classes `dl` (drawn line) and `dt` (drawn text) are the hooks the GSAP timelines in Landing.tsx animate. */

const FONT = { fontFamily: "var(--ff-inter), system-ui, sans-serif", fontWeight: 600, letterSpacing: ".04em" } as const;
const INK = "var(--color-on-surface)";
const SOFT = "var(--color-on-surface-variant)";
const HOT = "var(--color-primary)";

/** One stuck-list row, dimensioned. Ivory on the drenched hero. Synthetic example. */
export function RowDrawing() {
  return (
    <svg
      viewBox="24 24 530 310"
      role="img"
      aria-label="Drawing of one stuck list row with its parts labelled: who, why in plain words, source and the call button. Synthetic example."
      className="w-full h-auto text-on-primary"
    >
      <g fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
        <rect className="dl" x="40" y="90" width="400" height="120" rx="12" />
        <circle className="dl" cx="76" cy="150" r="18" />
        <rect className="dl" x="108" y="172" width="104" height="18" rx="9" />
        <rect className="dl" x="340" y="136" width="84" height="34" rx="8" />
        <path className="dl" d="M40 70 H440" />
        <path className="dl" d="M40 62 V78" />
        <path className="dl" d="M440 62 V78" />
        <path className="dl" d="M76 132 V60 H112" />
        <path className="dl" d="M160 210 V236 H120" />
        <path className="dl" d="M330 210 V280 H300" />
        <path className="dl" d="M424 153 H480 V110" />
      </g>
      <rect className="dt" x="340" y="136" width="84" height="34" rx="8" fill="currentColor" />
      <g fill="currentColor" style={FONT}>
        <text className="dt" x="76" y="155" textAnchor="middle" fontSize="13">AK</text>
        <text className="dt" x="108" y="140" fontSize="16">Asha K.</text>
        <text className="dt" x="108" y="160" fontSize="12" fontWeight="400" letterSpacing="0">Booked 9 days ago, no visit recorded</text>
        <text className="dt" x="160" y="185" textAnchor="middle" fontSize="11">2 days overdue</text>
        <text className="dt" x="224" y="185" fontSize="11" fontWeight="400" letterSpacing="0">Source: register row 41</text>
        <text className="dt" x="382" y="157" textAnchor="middle" fontSize="13" style={{ ...FONT, fill: HOT }}>Call</text>
        <text className="dt" x="240" y="60" textAnchor="middle" fontSize="11">ONE ROW</text>
        <text className="dt" x="116" y="42" fontSize="11">WHO</text>
        <text className="dt" x="40" y="252" fontSize="11">WHY, IN PLAIN WORDS</text>
        <text className="dt" x="150" y="296" fontSize="11">SOURCE, ALWAYS ONE CLICK AWAY</text>
        <text className="dt" x="446" y="100" fontSize="11">A PERSON ACTS</text>
        <text className="dt" x="40" y="322" fontSize="11" opacity=".75">SYNTHETIC EXAMPLE</text>
      </g>
    </svg>
  );
}

/** The gap, dimensioned along a day axis. x(day) = 48 + 32 * day. The marker group `#g-today` is moved by GSAP. */
export function GapTimeline() {
  const x = (d: number) => 48 + 32 * d;
  return (
    <svg
      viewBox="0 92 760 308"
      role="img"
      aria-label="Timeline drawing. A tumour board decision at day 0, a treatment booking expected by day 7, and a marker at day 16 with nothing booked, 9 days past the allowed gap. Synthetic example."
      className="w-full h-auto min-w-[620px] lg:min-w-0"
    >
      <g fill="none" strokeLinecap="round" strokeLinejoin="round">
        {/* axis and ticks */}
        <path className="g-axis" d={`M${x(0)} 250 H${x(21)}`} stroke={INK} strokeWidth="1.6" />
        {[0, 7, 14, 21].map((d) => (
          <path key={d} className="g-tick" d={`M${x(d)} 242 V258`} stroke={INK} strokeWidth="1.2" />
        ))}
        {/* allowed gap dimension */}
        <path className="g-allow" d={`M${x(0)} 168 H${x(7)}`} stroke={SOFT} strokeWidth="1.1" />
        <path className="g-allow" d={`M${x(0)} 160 V176`} stroke={SOFT} strokeWidth="1.1" />
        <path className="g-allow" d={`M${x(7)} 160 V176`} stroke={SOFT} strokeWidth="1.1" />
        <path className="g-ext" d={`M${x(0)} 176 V240`} stroke={SOFT} strokeWidth=".8" strokeDasharray="3 3" />
        <path className="g-ext" d={`M${x(7)} 176 V240`} stroke={SOFT} strokeWidth=".8" strokeDasharray="3 3" />
        {/* expected booking, empty until it is missed */}
        <circle className="g-exp" cx={x(7)} cy="250" r="9" stroke={SOFT} strokeWidth="1.4" strokeDasharray="3 3" fill="var(--color-background)" />
        {/* decision */}
        <circle className="g-node0" cx={x(0)} cy="250" r="9" fill={INK} stroke={INK} />
        {/* overdue stretch and its dimension */}
        <path className="g-over" d={`M${x(7)} 250 H${x(16)}`} stroke={HOT} strokeWidth="4.5" />
        <path className="g-overdim" d={`M${x(7)} 314 H${x(16)}`} stroke={HOT} strokeWidth="1.1" />
        <path className="g-overdim" d={`M${x(7)} 306 V322`} stroke={HOT} strokeWidth="1.1" />
        <path className="g-overdim" d={`M${x(16)} 306 V322`} stroke={HOT} strokeWidth="1.1" />
        {/* today marker */}
        <g id="g-today">
          <path d="M0 124 V292" stroke={INK} strokeWidth="1.2" />
          <path d="M-6 118 H6 L0 128 Z" fill={INK} stroke={INK} />
          <circle cx="0" cy="250" r="5" fill="var(--color-background)" stroke={INK} strokeWidth="1.6" />
        </g>
      </g>
      <g style={FONT} fontSize="13">
        {[0, 7, 14, 21].map((d) => (
          <text key={d} className="g-tickt" x={x(d)} y="282" textAnchor="middle" fill={SOFT}>DAY {d}</text>
        ))}
        <text className="g-node0t" x={x(0)} y="218" fill={INK}>TUMOUR BOARD DECISION</text>
        <text className="g-allowt" x={(x(0) + x(7)) / 2} y="150" textAnchor="middle" fill={SOFT}>ALLOWED GAP: 7 DAYS (PROPOSED)</text>
        <text className="g-expt" x={x(7)} y="218" fill={SOFT}>TREATMENT BOOKING EXPECTED</text>
        <text className="g-overt" x={(x(7) + x(16)) / 2} y="340" textAnchor="middle" fill={HOT}>9 DAYS PAST THE ALLOWED GAP</text>
        <text id="g-counter" x="0" y="110" textAnchor="middle" fill={INK}>DAY 16</text>
        <text x="48" y="384" fill={SOFT} opacity=".8">SYNTHETIC EXAMPLE</text>
      </g>
    </svg>
  );
}

/** Four hash-linked blocks, the third one changed, the link after it broken. */
export function ChainDrawing() {
  const blocks = [10, 86, 162, 238];
  return (
    <svg
      viewBox="0 0 300 130"
      role="img"
      aria-label="Four linked blocks. The third block is marked as changed and the link after it is broken."
      className="w-full h-auto"
    >
      <g fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.4">
        {blocks.map((bx, i) => (
          <rect
            key={bx}
            className="dl"
            x={bx}
            y="40"
            width="56"
            height="46"
            rx="8"
            stroke={i === 2 ? HOT : INK}
            fill={i === 2 ? "var(--color-primary-fixed)" : "var(--color-surface-container-lowest)"}
          />
        ))}
        <path className="dl" d="M66 63 H86" stroke={INK} />
        <path className="dl" d="M142 63 H162" stroke={INK} />
        <path className="dl" d="M218 63 H226 M230 63 H238" stroke={HOT} strokeDasharray="2 4" />
        <path className="dl" d="M222 55 L230 71 M230 55 L222 71" stroke={HOT} />
        {blocks.map((bx) => (
          <path key={`h${bx}`} className="dl" d={`M${bx + 10} 56 H${bx + 46} M${bx + 10} 66 H${bx + 34}`} stroke={SOFT} strokeWidth="1" />
        ))}
      </g>
      <g style={FONT} fontSize="9.5" textAnchor="middle">
        <text className="dt" x="38" y="108" fill={SOFT}>LINKED</text>
        <text className="dt" x="190" y="108" fill={HOT}>CHANGED</text>
        <text className="dt" x="228" y="28" fill={HOT}>CHAIN BREAKS HERE</text>
      </g>
    </svg>
  );
}

/** Exploded stack: models read, rules decide, people act. Parallelogram tiles, dashed corner lines. */
export function StackDrawing() {
  const W = 250;
  const D = 130;
  const tile = (x: number, y: number) =>
    `M${x} ${y} L${x + W * 0.94} ${y + W * 0.17} L${x + W * 0.94 - D * 0.34} ${y + W * 0.17 + D * 0.47} L${x - D * 0.34} ${y + D * 0.47} Z`;
  const x0 = 100;
  const ys = [26, 106, 186];
  const labels: [string, string[], boolean][] = [
    ["READS", ["OCR, vision, speech,", "column mapping"], false],
    ["DECIDES", ["pathway rules,", "plain SQL checks"], true],
    ["ACTS", ["coordinator, nurse,", "clinician"], false],
  ];
  return (
    <svg
      viewBox="0 0 580 330"
      role="img"
      aria-label="Exploded drawing of three layers. The top layer reads: OCR, vision, speech and column mapping. The middle layer decides: pathway rules and plain SQL checks. The bottom layer acts: coordinator, nurse and clinician."
      className="w-full h-auto"
    >
      <g fill="none" strokeLinecap="round" strokeLinejoin="round">
        {[0, 1].map((i) => (
          <g key={i} stroke={SOFT} strokeWidth=".9" strokeDasharray="3 4" className="dl">
            <path d={`M${x0} ${ys[i]} V${ys[i + 1]}`} />
            <path d={`M${x0 + W * 0.94} ${ys[i] + W * 0.17} V${ys[i + 1] + W * 0.17}`} />
            <path d={`M${x0 - D * 0.34} ${ys[i] + D * 0.47} V${ys[i + 1] + D * 0.47}`} />
          </g>
        ))}
        {ys.map((y, i) => (
          <path
            key={y}
            className="dl"
            d={tile(x0, y)}
            stroke={i === 1 ? HOT : INK}
            strokeWidth="1.6"
            fill={i === 1 ? "var(--color-primary-fixed)" : "var(--color-surface-container-lowest)"}
          />
        ))}
        {ys.map((y, i) => {
          const cx = x0 + (W * 0.94 + (W * 0.94 - D * 0.34) - D * 0.34) / 4;
          const cy = y + (W * 0.17 + (W * 0.17 + D * 0.47) + D * 0.47) / 4;
          return (
            <g key={`l${y}`} className="dl" stroke={i === 1 ? HOT : SOFT} strokeWidth="1">
              <path d={`M${cx} ${cy} H384`} />
              <circle cx={cx} cy={cy} r="2.5" fill={i === 1 ? HOT : SOFT} />
            </g>
          );
        })}
      </g>
      <g style={FONT}>
        {labels.map(([t, sub, hot], i) => {
          const y = ys[i] + (W * 0.17 + (W * 0.17 + D * 0.47) + D * 0.47) / 4;
          return (
            <g key={t} className="dt">
              <text x="392" y={y - 4} fontSize="12" fill={hot ? HOT : INK}>{t}</text>
              {sub.map((s, k) => (
                <text key={s} x="392" y={y + 12 + k * 13} fontSize="10.5" fontWeight="500" letterSpacing="0" fill={SOFT}>{s}</text>
              ))}
            </g>
          );
        })}
        <text className="dt" x="100" y="322" fontSize="10.5" fill={SOFT}>MODELS NEVER SET A FLAG, A RANK OR A MESSAGE</text>
      </g>
    </svg>
  );
}
