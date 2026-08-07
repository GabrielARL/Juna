#!/usr/bin/env python3
"""Build the self-contained BER-versus-SNR view.

Design notes that are decisions, not taste:

* Twelve panels: red1-red4, hydrophones 1-3, each at that path's best-BER
  geometry.
* Log BER axis. Zero-BER points are drawn at the half-error floor,
  0.5 / payload_bits, and marked hollow, so "no errors seen" is never confused
  with "measured this low".
* Four hues, five series. The two C,z arms are one receiver family -- the joint
  arm is the profiled arm plus a simultaneous step -- so they share the magenta
  and separate by line style and marker. A fifth hue cannot clear the CVD
  all-pairs check against blue, orange and magenta; composite encoding states
  the relationship the colours would have obscured.
* Palette values are the ones validated for the confirmation page.
"""
import argparse
import csv
import hashlib
import html
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

RECEIVERS = [
    ("ofdm_fec", "OFDM + FEC", "var(--recv-ofdm-fec)", "none", "circle"),
    ("pfft", "Partial-FFT + FEC", "var(--recv-pfft)", "none", "square"),
    ("lite", "JUNA-Lite", "var(--recv-lite)", "none", "circle"),
    ("profiled_cz", "JUNA (C,z) Joint gradient", "var(--recv-profiled-cz)",
     "none", "circle"),
    ("cwz_joint", "Juna joint (C,W,z)", "var(--recv-profiled-cz)",
     "5 3", "triangle"),
]

PANEL_W, PANEL_H = 300, 210
PAD_L, PAD_R, PAD_T, PAD_B = 44, 10, 12, 30


def load(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def panels(rows):
    """(channel, lane, objective) -> {receiver: [(snr, ber, bits, psr)]}"""
    out = {}
    for row in rows:
        key = (row["channel"], int(row["lane"]),
               row.get("objective", "min-BER"))
        entry = out.setdefault(key, {"series": {}, "geometry": None})
        entry["geometry"] = {k: row[k] for k in (
            "nfft", "cp", "code_rate", "outer_spacing", "inner_spacing",
            "check_degree", "horizon")}
        if "partial_fft_parts" in row:
            entry["geometry"]["partial_fft_parts"] = row["partial_fft_parts"]
        entry["series"].setdefault(row["algorithm_id"], []).append((
            float(row["snr_db"]), float(row["ber"]), int(row["payload_bits"]),
            float(row["psr"])))
    for entry in out.values():
        for series in entry["series"].values():
            series.sort()
    return out


def _floor(payload_bits):
    """Half-error measurement floor for a zero-error point."""
    return 0.5 / payload_bits if payload_bits else 1e-6


def coincident_groups(entry):
    """Receivers whose bit-error counts are identical at every SNR point.

    A group that coincides on every panel shares one drawing-plan entry and a
    combined legend label. A coincidence limited to one panel remains as
    separate series and is disclosed in that panel's note.
    """
    signatures = {}
    for rid, series in entry["series"].items():
        signatures.setdefault(tuple((s, b) for s, b, _p, _q in series),
                              []).append(rid)
    order = [r[0] for r in RECEIVERS]
    return [sorted(group, key=order.index)
            for group in signatures.values() if len(group) > 1]


def svg_panel(key, entry, ymin, ymax, snrs, plan):
    channel, lane, objective = key
    x0, x1 = min(snrs), max(snrs)
    w, h = PANEL_W - PAD_L - PAD_R, PANEL_H - PAD_T - PAD_B
    import math

    def sx(snr):
        return PAD_L + (snr - x0) / (x1 - x0) * w

    def sy(ber):
        lo, hi = math.log10(ymin), math.log10(ymax)
        v = min(max(math.log10(max(ber, ymin)), lo), hi)
        return PAD_T + (hi - v) / (hi - lo) * h

    parts = [f'<svg viewBox="0 0 {PANEL_W} {PANEL_H}" role="img" '
             f'aria-label="{html.escape(channel)} hydrophone {lane}, '
             f'bit error rate versus added-noise SNR">']
    # decade gridlines
    decade = math.floor(math.log10(ymin))
    while 10 ** decade <= ymax:
        if 10 ** decade >= ymin:
            y = sy(10 ** decade)
            parts.append(f'<line class="grid" x1="{PAD_L}" y1="{y:.1f}" '
                         f'x2="{PAD_L + w}" y2="{y:.1f}"/>')
            parts.append(f'<text class="tick" x="{PAD_L - 6}" y="{y + 3:.1f}" '
                         f'text-anchor="end">1e{decade}</text>')
        decade += 1
    for snr in snrs:
        if snr % 10:
            continue
        parts.append(f'<text class="tick" x="{sx(snr):.1f}" '
                     f'y="{PANEL_H - PAD_B + 14}" text-anchor="middle">'
                     f'{int(snr)}</text>')
    parts.append(f'<line class="axis" x1="{PAD_L}" y1="{PAD_T + h}" '
                 f'x2="{PAD_L + w}" y2="{PAD_T + h}"/>')

    for rid, label, colour, dash, marker in plan:
        series = entry["series"].get(rid)
        if not series:
            continue
        width = 2
        pts, hollow = [], []
        for snr, ber, bits, _psr in series:
            zero = ber <= 0
            value = _floor(bits) if zero else ber
            pts.append((sx(snr), sy(value)))
            hollow.append(zero)
        d = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}"
                     for i, (x, y) in enumerate(pts))
        dash_attr = f' stroke-dasharray="{dash}"' if dash != "none" else ""
        parts.append(f'<path class="series" d="{d}" stroke="{colour}" '
                     f'stroke-width="{width}"{dash_attr}/>')
        for (x, y), is_zero in zip(pts, hollow):
            fill = "var(--surface-1)" if is_zero else colour
            if marker == "square":
                parts.append(f'<rect x="{x-2.6:.1f}" y="{y-2.6:.1f}" width="5.2" '
                             f'height="5.2" fill="{fill}" stroke="{colour}"/>')
            elif marker == "diamond":
                parts.append(f'<polygon points="{x:.1f},{y-3.4:.1f} '
                             f'{x+3.1:.1f},{y:.1f} {x:.1f},{y+3.4:.1f} '
                             f'{x-3.1:.1f},{y:.1f}" '
                             f'fill="{fill}" stroke="{colour}"/>')
            elif marker == "triangle":
                parts.append(f'<polygon points="{x:.1f},{y-3.2:.1f} '
                             f'{x-3:.1f},{y+2.4:.1f} {x+3:.1f},{y+2.4:.1f}" '
                             f'fill="{fill}" stroke="{colour}"/>')
            else:
                parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.8" '
                             f'fill="{fill}" stroke="{colour}"/>')
    parts.append("</svg>")
    return "".join(parts)


def draw_plan(data):
    """One entry per distinct result: (rid, label, colour, dash, marker).

    Receivers whose curves coincide on every panel share one plotted path and
    a combined legend label. A coincidence on only some panels is not merged,
    because those curves differ elsewhere.
    """
    order = [r[0] for r in RECEIVERS]
    spec = {rid: (lbl, c, d, m) for rid, lbl, c, d, m in RECEIVERS}
    per_panel = [{frozenset(g) for g in coincident_groups(entry)}
                 for entry in data.values()]
    shared = set.intersection(*per_panel) if per_panel else set()

    merged, plan = set(), []
    for rid in order:
        if rid in merged or not any(rid in e["series"] for e in data.values()):
            continue
        group = next((g for g in shared if rid in g), None)
        label, colour, dash, marker = spec[rid]
        if group:
            members = [r for r in order if r in group]
            label = " = ".join(spec[r][0] for r in members)
            merged.update(group)
        plan.append((rid, label, colour, dash, marker))
    return plan


def render(rows, configuration_only=False):
    import math
    data = panels(rows)
    plan = draw_plan(data)
    snrs = sorted({float(r["snr_db"]) for r in rows})
    values = [float(r["ber"]) for r in rows if float(r["ber"]) > 0]
    floors = [_floor(int(r["payload_bits"])) for r in rows
              if float(r["ber"]) <= 0]
    ymin = 10 ** math.floor(math.log10(min(values + floors)))
    ymax = 10 ** math.ceil(math.log10(max(values)))

    cards = []
    for key in sorted(data):
        entry = data[key]
        g = entry["geometry"]
        horizon = ("fill" if configuration_only and g["horizon"] == "0"
                   else g["horizon"])
        geometry = (f"N={g['nfft']} · CP={g['cp']} · rate={g['code_rate']} · "
                    f"pilots={g['outer_spacing']}/{g['inner_spacing']} · "
                    f"dc={g['check_degree']} · K={horizon}")
        if "partial_fft_parts" in g:
            geometry += f" · PFFT parts={g['partial_fft_parts']}"
        objective = key[2]
        aim = ("held at the printed configuration" if configuration_only else
               "held at the configuration with the lowest 20 dB BER"
               if objective == "min-BER" else
               "held at the configuration with the highest 20 dB effective rate")
        title_suffix = "" if configuration_only else f" — {html.escape(objective)}"
        cards.append(
            f'<figure class="panel"><figcaption><b>{html.escape(key[0])} '
            f'hydrophone {key[1]}{title_suffix}</b>'
            f'<span>{html.escape(geometry)}</span>'
            f'<span class="aim">{html.escape(aim)}</span>'
            f'</figcaption>{svg_panel(key, entry, ymin, ymax, snrs, plan)}</figure>')

    def legend_entry(label, colour, dash):
        dash_attr = "" if dash == "none" else f' stroke-dasharray="{dash}"'
        return (f'<span><svg width="26" height="10" aria-hidden="true">'
                f'<line x1="1" y1="5" x2="25" y2="5" stroke="{colour}" '
                f'stroke-width="2"{dash_attr}/></svg>'
                f'{html.escape(label)}</span>')

    legend = "".join(legend_entry(lbl, c, d)
                     for _rid, lbl, c, d, _m in plan)

    table_rows = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(r[c]))}</td>" for c in (
            "channel", "lane", "snr_db", "algorithm_id", "psr", "ber",
            "payload_bits", "bit_errors", "decode_failures")) + "</tr>"
        for r in rows)

    names = {rid: lbl for rid, lbl, _c, _d, _m in RECEIVERS}
    notes = []
    for key in sorted(data):
        for group in coincident_groups(data[key]):
            listed = ", ".join(names[rid] for rid in group)
            notes.append(f"{key[0]} hydrophone {key[1]} ({key[2]}): {listed} returned "
                         f"identical bit-error counts at every SNR point. "
                         f"Their plotted paths coincide in this panel; the "
                         f"legend identifies each receiver.")
    coincidence = ("<p><b>Coincident curves.</b> " + " ".join(notes) + "</p>"
                   if notes else "")

    paths = sorted({(k[0], k[1]) for k in data})
    aims = sorted({k[2] for k in data})
    requested_paths = {(f"red{channel}", lane)
                       for channel in range(1, 5) for lane in range(1, 4)}
    if set(paths) == requested_paths:
        scope = "red1-red4, hydrophones 1-3 — 12 capture–hydrophone paths"
    else:
        scope = (f"{len(paths)} of 12 requested capture–hydrophone paths "
                 f"(red1-red4, hydrophones 1-3)")
    if len(aims) > 1:
        scope += f", at {' and '.join(aims)} geometries"
    frames = sorted({int(r["frames"]) for r in rows})
    geometry_note = (
        "Each panel uses the configuration printed above its axes."
        if configuration_only else
        "Each panel is held at the configuration with the lowest\n20 dB BER, "
        "printed above its axes.")
    return TEMPLATE.format(
        panels="".join(cards), legend=legend, table_rows=table_rows,
        row_count=len(rows), path_count=len(data), scope=scope,
        coincidence=coincidence,
        grid_class=("single" if len(data) == 1
                    else "pair" if len(data) == 2 else ""),
        frames="/".join(str(f) for f in frames),
        receivers=len({r["algorithm_id"] for r in rows}),
        snr_lo=int(min(snrs)), snr_hi=int(max(snrs)),
        geometry_note=geometry_note)


TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Red replay channel: BER versus added-noise SNR</title>
<style>
  :root {{ color-scheme: light dark; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font: 14px/1.5 system-ui, sans-serif; }}
  .viz-root {{
    color-scheme: light;
    --surface-1: #fcfcfb; --surface-2: #f3f2ef;
    --text-primary: #0b0b0b; --text-secondary: #52514e;
    --grid: #dcdad4; --axis: #b8b6ae;
    --recv-ofdm-fec: #226fca; --recv-lite: #d95b28; --recv-pfft: #65645f;
    --recv-profiled-cz: #a6307e;
    background: var(--surface-1); color: var(--text-primary);
    padding: 22px; min-height: 100vh;
  }}
  @media (prefers-color-scheme: dark) {{
    :root:where(:not([data-theme="light"])) .viz-root {{
      color-scheme: dark;
      --surface-1: #191918; --surface-2: #242422;
      --text-primary: #fff; --text-secondary: #c6c5bc;
      --grid: #41413d; --axis: #55554f;
      --recv-ofdm-fec: #4b97ec; --recv-lite: #ef7542; --recv-pfft: #b3b2aa;
      --recv-profiled-cz: #d368af;
    }}
  }}
  :root[data-theme="dark"] .viz-root {{
    color-scheme: dark;
    --surface-1: #191918; --surface-2: #242422;
    --text-primary: #fff; --text-secondary: #c6c5bc;
    --grid: #41413d; --axis: #55554f;
    --recv-ofdm-fec: #4b97ec; --recv-lite: #ef7542; --recv-pfft: #b3b2aa;
    --recv-profiled-cz: #d368af;
  }}
  h1 {{ font-size: 20px; margin: 0 0 6px; }}
  .provenance {{ background: var(--surface-2); border-radius: 8px;
    padding: 12px 15px; margin: 12px 0 18px; max-width: 78ch;
    color: var(--text-secondary); font-size: 13px; }}
  .provenance b {{ color: var(--text-primary); }}
  .provenance p {{ margin: 6px 0; }}
  .legend {{ display: flex; gap: 18px; flex-wrap: wrap; margin: 0 0 14px;
    color: var(--text-secondary); font-size: 13px; }}
  .legend span {{ display: inline-flex; align-items: center; gap: 7px;
    white-space: nowrap; }}
  .legend svg {{ flex: none; width: 26px; }}
  .grid-panels {{ display: grid; gap: 12px;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); }}
  .grid-panels.single {{ grid-template-columns: minmax(320px, 620px); }}
  .grid-panels.pair {{ grid-template-columns: repeat(auto-fit, minmax(330px, 1fr)); }}
  .panel {{ margin: 0; background: var(--surface-2); border-radius: 8px;
    padding: 8px 6px 2px; }}
  .panel figcaption {{ display: flex; flex-direction: column; gap: 1px;
    padding: 0 8px 2px; font-size: 12px; color: var(--text-secondary); }}
  .panel figcaption b {{ color: var(--text-primary); font-size: 13px; }}
  .panel figcaption .aim {{ font-size: 11px; }}
  svg {{ width: 100%; height: auto; display: block; }}
  .grid {{ stroke: var(--grid); stroke-width: 1; }}
  .axis {{ stroke: var(--axis); stroke-width: 1; }}
  .tick {{ fill: var(--text-secondary); font-size: 9px; }}
  .series {{ fill: none; stroke-width: 2; }}
  .axis-title {{ color: var(--text-secondary); font-size: 12px;
    margin: 10px 0 0; }}
  details {{ margin-top: 20px; }}
  table {{ border-collapse: collapse; font-size: 12px; margin-top: 10px;
    width: 100%; }}
  th, td {{ border-bottom: 1px solid var(--grid); padding: 3px 6px;
    text-align: left; }}
  .scroll {{ overflow-x: auto; max-height: 460px; }}
</style></head>
<body><div class="viz-root">
<h1>Red replay channel: BER versus added-noise SNR</h1>
<p class="axis-title">{scope}, {receivers} receivers, {snr_lo}:2:{snr_hi} dB,
seed 4, {frames} frames per point.</p>

<div class="provenance">
<p><b>Different channel-application path from the Results page. Do not plot
these curves against the 20 dB confirmation numbers.</b> Those run through the
harness's own replay and Gaussian noise; these run through the uwa-channels
mixing model.</p>
<p><b>Noise.</b> The <code>red_noise.mat</code> model from the same Zenodo
record as the captures: α = 1.7, so the noise is <b>impulsive</b>, not
Gaussian, and correlated across the three hydrophones. Each path decodes one
hydrophone, so what reaches the receiver is that hydrophone's coloured,
heavy-tailed marginal; the array correlation is present in the model but is
not exercised by a single-lane receiver.</p>
<p><b>SNR.</b> Signal power over the α-stable pseudo-power 2δ², after
Mahmood &amp; Chitre, <i>Optimal and Near-Optimal Detection in Bursty
Impulsive Noise</i>, IEEE JOE 42(3) 2017, eq. (35). A variance-based SNR is
undefined here: second-order moments do not exist for α &lt; 2.</p>
<p><b>Geometry.</b> {geometry_note}</p>
{coincidence}
<p><b>Reading.</b> Hollow markers are points where no bit errors were
observed; they are drawn at the half-error floor 0.5/payload bits, which is a
measurement limit, not a measured value.</p>
</div>

<div class="legend">{legend}</div>
<div class="grid-panels {grid_class}">{panels}</div>
<p class="axis-title">Horizontal: added-noise SNR (dB). Vertical: payload BER,
log scale.</p>

<details><summary>Data table — {row_count} rows over {path_count} paths</summary>
<div class="scroll"><table><thead><tr><th>channel</th><th>lane</th>
<th>SNR dB</th><th>receiver</th><th>PSR</th><th>BER</th><th>payload bits</th>
<th>bit errors</th><th>decode failures</th></tr></thead>
<tbody>{table_rows}</tbody></table></div></details>
</div></body></html>
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default=os.path.join(
        HERE, "red_snr_sweep_uwa_noise.csv"))
    parser.add_argument("--out", default=os.path.join(HERE, "sweep_view.html"))
    parser.add_argument("--configuration-only", action="store_true")
    args = parser.parse_args()
    rows = load(args.csv)
    if not rows:
        raise SystemExit("no rows in " + args.csv)
    html_text = render(rows, configuration_only=args.configuration_only)
    with open(args.out, "w", encoding="utf-8") as handle:
        handle.write(html_text)
    digest = hashlib.sha256(open(args.csv, "rb").read()).hexdigest()
    print(f"wrote {args.out} ({len(html_text)/1e3:.0f} kB, {len(rows)} rows)")
    print(f"source sha256 {digest[:16]}…")


if __name__ == "__main__":
    main()
