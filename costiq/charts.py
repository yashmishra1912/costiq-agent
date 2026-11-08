"""Plotly figures for the report. Light, print-oriented consulting style.

Colour roles (validated reference palette, light mode):
- target company = series blue; peers = neutral grey; peer median = dark ink dashed
- composition stacks use categorical slots 1-6 in fixed order
- heatmap = diverging blue (better) <-> grey <-> red (worse)
"""
from __future__ import annotations

import plotly.graph_objects as go

from .schema import PCT_RATIOS, RATIOS

INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#8a8984"
GRID = "#e6e5e1"
SURFACE = "#ffffff"
TARGET = "#2a78d6"
PEER = "#b9b8b2"
CATS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
DIV_NEG, DIV_MID, DIV_POS = "#2a78d6", "#f0efec", "#e34948"
FONT = "Inter, -apple-system, Segoe UI, Roboto, Arial, sans-serif"


def _layout(fig: go.Figure, title: str, height: int = 360, **kw) -> go.Figure:
    base = dict(
        title={"text": title, "x": 0, "xanchor": "left", "font": {"size": 15, "color": INK}},
        font={"family": FONT, "size": 12, "color": INK2},
        paper_bgcolor=SURFACE, plot_bgcolor=SURFACE, height=height,
        margin={"l": 10, "r": 20, "t": 50, "b": 10},
        hoverlabel={"bgcolor": "white", "font": {"color": INK}},
        legend={"orientation": "h", "y": -0.15, "x": 0},
        bargap=0.35)
    base.update(kw)
    fig.update_layout(**base)
    fig.update_xaxes(gridcolor=GRID, zeroline=False, linecolor=GRID, automargin=True)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor=GRID, automargin=True)
    return fig


def _fmt(key: str, v):
    if v is None:
        return None
    return v * 100 if key in PCT_RATIOS else v


def _unit(key: str) -> str:
    return "%" if key in PCT_RATIOS else ("days" if key.endswith("_days") else "")


def ratio_bar(row: dict, target_name: str) -> go.Figure | None:
    """Horizontal bars: target vs each peer, with peer median line."""
    key = row["key"]
    pts = [(target_name, row["target"], True)] + [(n, v, False) for n, v in row["peers"].items()]
    pts = [(n, _fmt(key, v), t) for n, v, t in pts if v is not None]
    if len(pts) < 2:
        return None
    pts.sort(key=lambda p: p[1])
    u = _unit(key)
    fig = go.Figure(go.Bar(
        x=[p[1] for p in pts], y=[p[0] for p in pts], orientation="h",
        marker={"color": [TARGET if p[2] else PEER for p in pts], "line": {"color": SURFACE, "width": 2}},
        text=[f"{p[1]:,.1f}{u if u == '%' else ''}" for p in pts], textposition="outside",
        textfont={"color": INK2}, cliponaxis=False,
        hovertemplate="%{y}: %{x:,.2f}" + (u if u == "%" else " " + u) + "<extra></extra>"))
    med = _fmt(key, row["median"])
    if med is not None:
        fig.add_vline(x=med, line={"color": INK, "dash": "dash", "width": 1.5},
                      annotation_text=f"Peer median {med:,.1f}", annotation_position="top",
                      annotation_font={"size": 11, "color": INK})
    return _layout(fig, row["label"] + (f" ({u})" if u else ""), height=60 + 38 * len(pts),
                   showlegend=False)


def trend_small_multiples(target_cr: dict, comp_crs: list[dict], keys: list[str]) -> go.Figure:
    """Target vs peer median over the last three years, one panel per ratio."""
    from plotly.subplots import make_subplots
    import statistics

    keys = [k for k in keys if any(y["ratios"].get(k) is not None for y in target_cr["years"])]
    cols = 3
    rows = max(1, -(-len(keys) // cols))
    fig = make_subplots(rows=rows, cols=cols, subplot_titles=[RATIOS[k][0] for k in keys],
                        horizontal_spacing=0.08, vertical_spacing=0.18)
    for i, k in enumerate(keys):
        r, c = i // cols + 1, i % cols + 1
        xs = [y["fy"] for y in target_cr["years"]]
        ts = [_fmt(k, y["ratios"].get(k)) for y in target_cr["years"]]
        # peer median by position (oldest -> newest), aligned on index from the end
        meds = []
        n = len(xs)
        for j in range(n):
            vals = []
            for cr in comp_crs:
                idx = len(cr["years"]) - n + j
                if 0 <= idx < len(cr["years"]):
                    v = cr["years"][idx]["ratios"].get(k)
                    if v is not None:
                        vals.append(_fmt(k, v))
            meds.append(statistics.median(vals) if len(vals) >= 2 else None)
        fig.add_trace(go.Scatter(x=xs, y=meds, name="Peer median", mode="lines+markers",
                                 line={"color": MUTED, "width": 2, "dash": "dash"},
                                 marker={"size": 8, "color": MUTED}, showlegend=(i == 0),
                                 hovertemplate="Peer median %{x}: %{y:,.1f}<extra></extra>"), r, c)
        fig.add_trace(go.Scatter(x=xs, y=ts, name=target_cr["name"], mode="lines+markers",
                                 line={"color": TARGET, "width": 2.5}, marker={"size": 9, "color": TARGET},
                                 showlegend=(i == 0),
                                 hovertemplate=target_cr["name"] + " %{x}: %{y:,.1f}<extra></extra>"), r, c)
    fig.update_annotations(font={"size": 12, "color": INK})
    return _layout(fig, "Three-year trend: target vs peer median (% of revenue unless stated)",
                   height=260 * rows + 60)


COMPOSITION = [("Material / COGS", "cogs"), ("Employee", "employee"), ("Other operating", "other"),
               ("D&A", "dep"), ("Finance cost", "fin"), ("Pre-tax margin & other", "rest")]


def composition(target_cr: dict, comp_crs: list[dict]) -> go.Figure | None:
    """100% stacked bar of where each revenue rupee goes (latest FY)."""
    names, data = [], {k: [] for _, k in COMPOSITION}
    for cr in [target_cr, *comp_crs]:
        if not cr["years"]:
            continue
        y = cr["years"][-1]
        raw, der = y["raw"], y["derived"]
        rev, cogs, emp = raw.get("revenue"), der.get("cogs_used"), raw.get("employee_cost")
        ebitda, dep, fin = der.get("ebitda_used"), raw.get("depreciation"), raw.get("finance_cost")
        if None in (rev, cogs, emp, ebitda, dep, fin) or not rev:
            continue
        other = rev - ebitda - cogs - emp
        rest = ebitda - dep - fin
        vals = dict(cogs=cogs, employee=emp, other=other, dep=dep, fin=fin, rest=rest)
        names.append(cr["name"] + (" (target)" if cr is target_cr else ""))
        for k in data:
            data[k].append(vals[k] / rev * 100)
    if len(names) < 2:
        return None
    fig = go.Figure()
    for i, (label, k) in enumerate(COMPOSITION):
        fig.add_trace(go.Bar(y=names, x=data[k], name=label, orientation="h",
                             marker={"color": CATS[i], "line": {"color": SURFACE, "width": 2}},
                             hovertemplate="%{y}<br>" + label + ": %{x:.1f}% of revenue<extra></extra>"))
    fig.update_layout(barmode="relative")
    fig.update_xaxes(ticksuffix="%")
    fig.update_yaxes(autorange="reversed")
    return _layout(fig, "Cost composition - share of revenue, latest FY (companies with full disclosure)",
                   height=120 + 46 * len(names))


def heatmap(rows: list[dict], target_name: str) -> go.Figure | None:
    """Deviation of each company from peer median, oriented so red = worse, blue = better."""
    use = [r for r in rows if r["direction"] in ("lower", "higher") and r["median"] and r["peer_count"] >= 2]
    if not use:
        return None
    names = [target_name] + list(use[0]["peers"].keys())
    z, txt = [], []
    for r in use:
        sign = 1 if r["direction"] == "lower" else -1
        zr, tr = [], []
        for n in names:
            v = r["target"] if n == target_name else r["peers"].get(n)
            if v is None:
                zr.append(None)
                tr.append("n/d")
            else:
                rel = (v - r["median"]) / abs(r["median"]) * sign
                zr.append(max(-1, min(1, rel / 0.3)))
                tr.append(f"{_fmt(r['key'], v):,.1f}")
        z.append(zr)
        txt.append(tr)
    fig = go.Figure(go.Heatmap(
        z=z, x=[n + (" ★" if n == target_name else "") for n in names], y=[r["label"] for r in use],
        text=txt, texttemplate="%{text}", textfont={"size": 11, "color": INK},
        colorscale=[[0, DIV_NEG], [0.5, DIV_MID], [1, DIV_POS]], zmin=-1, zmax=1,
        xgap=2, ygap=2, hoverongaps=False,
        colorbar={"title": "vs median", "tickvals": [-1, 0, 1],
                  "ticktext": ["≥30% better", "At median", "≥30% worse"], "len": 0.6},
        hovertemplate="%{x}<br>%{y}: %{text}<extra></extra>"))
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(side="top", tickangle=0)
    return _layout(fig, "Benchmarking heatmap - value shown; colour = relative position vs peer median",
                   height=90 + 30 * len(use))


def gap_chart(gaps: list[dict], ccy: str, div: float = 1.0) -> go.Figure | None:
    if not gaps:
        return None
    g = gaps[:8][::-1]
    fig = go.Figure(go.Bar(
        x=[x["gap_value_m"] / div for x in g], y=[x["label"] for x in g], orientation="h",
        marker={"color": DIV_POS, "line": {"color": SURFACE, "width": 2}},
        text=[f"+{x['gap_pp']:.1f} pp · {x['gap_value_m'] / div:,.0f}" for x in g], textposition="outside",
        cliponaxis=False, textfont={"color": INK2},
        hovertemplate="%{y}<br>Excess vs median: %{x:,.0f} " + ccy + " m<extra></extra>"))
    return _layout(fig, f"Cost gaps vs peer median - excess spend at target's revenue ({ccy})",
                   height=100 + 44 * len(g), showlegend=False)


def waterfall(sv: dict, ccy: str, scenario: str = "Moderate", div: float = 1.0) -> go.Figure | None:
    items = [i for i in sv["items"] if i["counted"] and i["type"] == "pnl" and i["scenarios"][scenario] > 0]
    if not items:
        return None
    items.sort(key=lambda i: i["scenarios"][scenario], reverse=True)
    x = [i["title"][:38] + ("…" if len(i["title"]) > 38 else "") for i in items] + ["Total potential"]
    y = [i["scenarios"][scenario] / div for i in items] + [0]
    fig = go.Figure(go.Waterfall(
        x=x, y=y, measure=["relative"] * len(items) + ["total"],
        increasing={"marker": {"color": TARGET}}, totals={"marker": {"color": INK2}},
        connector={"line": {"color": GRID}},
        text=[f"{v:,.0f}" for v in y[:-1]] + [f"{sum(y):,.0f}"], textposition="outside", cliponaxis=False,
        hovertemplate="%{x}: %{y:,.0f} " + ccy + "<extra></extra>"))
    return _layout(fig, f"Potential annual savings build-up - {scenario} scenario ({ccy}, not guaranteed)",
                   height=420, showlegend=False)


def priority_matrix(recs: list[dict]) -> go.Figure | None:
    lv = {"low": 1, "medium": 2, "high": 3}
    pts = []
    for i, r in enumerate(recs):
        imp = lv.get(str(r.get("impact", "")).lower())
        dif = lv.get(str(r.get("difficulty", "")).lower())
        if imp and dif:
            pts.append((dif, imp, f"R{i + 1}", r.get("title", "")))
    if not pts:
        return None
    # jitter overlapping points
    seen: dict = {}
    xs, ys = [], []
    for d, im, *_ in pts:
        k = (d, im)
        n = seen.get(k, 0)
        seen[k] = n + 1
        xs.append(d + (n % 3 - 1) * 0.18)
        ys.append(im + (n // 3) * 0.18)
    fig = go.Figure(go.Scatter(
        x=xs, y=ys, mode="markers+text", text=[p[2] for p in pts], textposition="middle center",
        textfont={"color": "white", "size": 11},
        marker={"size": 30, "color": TARGET, "line": {"color": SURFACE, "width": 2}},
        customdata=[p[3] for p in pts], hovertemplate="%{text}: %{customdata}<extra></extra>"))
    for x0, y0, label in [(0.5, 2.5, "Quick wins"), (2.5, 2.5, "Major projects"),
                          (0.5, 0.5, "Fill-ins"), (2.5, 0.5, "Deprioritise")]:
        fig.add_annotation(x=x0 + 0.05, y=y0 + 0.95, text=label, showarrow=False, xanchor="left",
                           font={"size": 11, "color": MUTED})
    fig.add_shape(type="line", x0=2, x1=2, y0=0.5, y1=3.5, line={"color": GRID, "width": 1.5})
    fig.add_shape(type="line", x0=0.5, x1=3.5, y0=2, y1=2, line={"color": GRID, "width": 1.5})
    fig.update_xaxes(range=[0.5, 3.5], tickvals=[1, 2, 3], ticktext=["Low", "Medium", "High"],
                     title="Implementation difficulty", showgrid=False)
    fig.update_yaxes(range=[0.5, 3.5], tickvals=[1, 2, 3], ticktext=["Low", "Medium", "High"],
                     title="Impact", showgrid=False)
    return _layout(fig, "Implementation priority matrix", height=420, showlegend=False)


def revenue_trend(target_cr: dict, comp_crs: list[dict], ccy: str, div: float = 1.0) -> go.Figure:
    fig = go.Figure()

    def xy(cr):
        return ([y.get("period_end") or y["fy"] for y in cr["years"]],
                [(y["raw"].get("revenue") or 0) / div if y["raw"].get("revenue") is not None else None for y in cr["years"]],
                [y["fy"] for y in cr["years"]])
    for cr in comp_crs:
        x, yv, fy = xy(cr)
        fig.add_trace(go.Scatter(x=x, y=yv, customdata=fy,
                                 text=[""] * (len(x) - 1) + [cr["name"]], textposition="middle right",
                                 textfont={"size": 11, "color": INK2}, cliponaxis=False,
                                 name=cr["name"], mode="lines+markers+text", showlegend=False, line={"color": PEER, "width": 2},
                                 marker={"size": 8, "color": PEER},
                                 hovertemplate=cr["name"] + " %{customdata}: %{y:,.0f}<extra></extra>"))
    x, yv, fy = xy(target_cr)
    fig.add_trace(go.Scatter(x=x, y=yv, customdata=fy,
                             name=target_cr["name"] + " (target)", mode="lines+markers",
                             line={"color": TARGET, "width": 3}, marker={"size": 9, "color": TARGET},
                             hovertemplate=target_cr["name"] + " %{customdata}: %{y:,.0f}<extra></extra>"))
    return _layout(fig, f"Revenue by financial-year end date ({ccy})",
                   height=380)


# ------------------------------------------------------------ infographics
GOOD, PAR, BAD = "#0ca30c", "#b9b8b2", "#d03b3b"
SEQ = ["#9ec5f4", "#3987e5", "#1c5cab"]  # sequential blue: conservative -> optimistic


def competitiveness_score(rows: list[dict]) -> float | None:
    """Share of benchmarked metrics where the target is better (1) or at par (0.5) vs peers."""
    b = sum(1 for r in rows if r["status"] == "Better")
    p = sum(1 for r in rows if r["status"] == "At par")
    w = sum(1 for r in rows if r["status"] == "Worse")
    n = b + p + w
    return round((b + 0.5 * p) / n * 100) if n else None


def score_gauge(rows: list[dict], height: int = 270) -> go.Figure | None:
    s = competitiveness_score(rows)
    if s is None:
        return None
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=s, number={"suffix": "/100", "font": {"size": 34, "color": INK}},
        gauge={"axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": MUTED, "tickvals": [0, 40, 60, 100]},
               "bar": {"color": INK, "thickness": 0.22},
               "steps": [{"range": [0, 40], "color": "#f6c9c9"}, {"range": [40, 60], "color": "#fbe7b5"},
                         {"range": [60, 100], "color": "#cdeccd"}],
               "borderwidth": 0}))
    return _layout(fig, "Cost competitiveness score<br><span style='font-size:11px;color:#8a8984'>"
                        "share of metrics better (1) or at par (½) vs peer median · &lt;40 lagging · 40–60 mixed · &gt;60 ahead</span>",
                   height=height, margin={"l": 30, "r": 30, "t": 82, "b": 10})


def status_donut(rows: list[dict], height: int = 270) -> go.Figure | None:
    counts = [("Better", GOOD), ("At par", PAR), ("Worse", BAD)]
    vals = [sum(1 for r in rows if r["status"] == k) for k, _ in counts]
    if not sum(vals):
        return None
    fig = go.Figure(go.Pie(
        labels=[f"{k} than peers" if k != "At par" else "At par" for k, _ in counts], values=vals, hole=0.62,
        marker={"colors": [c for _, c in counts], "line": {"color": SURFACE, "width": 3}},
        textinfo="value", textfont={"size": 14, "color": "white"}, sort=False,
        hovertemplate="%{label}: %{value} metrics<extra></extra>"))
    fig.add_annotation(text=f"<b>{sum(vals)}</b><br>metrics", showarrow=False, font={"size": 14, "color": INK})
    fig.update_layout(legend={"orientation": "h", "y": -0.08, "x": 0.5, "xanchor": "center"})
    return _layout(fig, "Benchmark scorecard", height=height)


def revenue_donut(target_cr: dict, ccy_symbol: str = "₹", height: int = 270) -> go.Figure | None:
    """Where every 100 units of revenue go (latest FY, target)."""
    if not target_cr["years"]:
        return None
    y = target_cr["years"][-1]
    raw, der = y["raw"], y["derived"]
    rev, cogs, emp = raw.get("revenue"), der.get("cogs_used"), raw.get("employee_cost")
    ebitda, dep, fin = der.get("ebitda_used"), raw.get("depreciation"), raw.get("finance_cost")
    if None in (rev, cogs, emp, ebitda, dep, fin) or not rev:
        return None
    parts = [("Materials / COGS", cogs), ("Employees", emp), ("Other operating", rev - ebitda - cogs - emp),
             ("Depreciation", dep), ("Finance cost", fin), ("Pre-tax profit & other", ebitda - dep - fin)]
    parts = [(k, v / rev * 100) for k, v in parts]
    fig = go.Figure(go.Pie(
        labels=[k for k, _ in parts], values=[max(v, 0) for _, v in parts], hole=0.55, sort=False,
        marker={"colors": CATS[:6], "line": {"color": SURFACE, "width": 3}},
        texttemplate="%{value:.0f}", textfont={"size": 12, "color": "white"},
        hovertemplate="%{label}: " + ccy_symbol + "%{value:.1f} of every " + ccy_symbol + "100<extra></extra>"))
    fig.add_annotation(text=f"<b>{ccy_symbol}100</b><br>of revenue", showarrow=False, font={"size": 13, "color": INK},
                       x=0.34, y=0.5, xref="paper", yref="paper")
    fig = _layout(fig, f"Where every {ccy_symbol}100 of revenue goes ({y['fy']})", height=height)
    fig.update_layout(legend={"orientation": "v", "x": 0.72, "y": 0.5, "font": {"size": 11}},
                      margin={"l": 0, "r": 0, "t": 50, "b": 10})
    fig.update_traces(domain={"x": [0, 0.68]})
    return fig


def scenario_bars(sv: dict, unit_label: str, div: float = 1.0, height: int = 270) -> go.Figure | None:
    p = sv.get("totals", {}).get("pnl", {})
    if not p or not any(p.values()):
        return None
    ks = ["Conservative", "Moderate", "Optimistic"]
    vals = [p.get(k, 0) / div for k in ks]
    fig = go.Figure(go.Bar(
        x=ks, y=vals, marker={"color": SEQ, "line": {"color": SURFACE, "width": 2}},
        text=[f"{v:,.0f}" for v in vals], textposition="outside", cliponaxis=False,
        textfont={"size": 14, "color": INK}, hovertemplate="%{x}: %{y:,.0f} " + unit_label + "<extra></extra>"))
    fig = _layout(fig, f"Potential annual savings ({unit_label})", height=height, showlegend=False, bargap=0.45)
    fig.update_yaxes(visible=False)
    fig.update_xaxes(showgrid=False)
    return fig
