"""Renders the 10-section consulting report as a single self-contained HTML file."""
from __future__ import annotations

import html
from datetime import date

import plotly.io as pio
from plotly.offline import get_plotlyjs

from . import charts
from .schema import LINE_ITEMS, PCT_RATIOS, RATIOS


def esc(x) -> str:
    return html.escape("" if x is None else str(x))


def safe_url(u) -> str:
    """Only http(s) links survive - model-supplied URLs are untrusted."""
    u = str(u or "").strip()
    return html.escape(u) if u.lower().startswith(("http://", "https://")) else ""


def money_unit(ccy: str) -> tuple[float, str]:
    """Divisor applied to base-currency millions, and display label."""
    if (ccy or "").upper() == "INR":
        return 10.0, "₹ crore"
    return 1.0, f"{ccy} million"


def fmt_ratio(key: str, v) -> str:
    if v is None:
        return '<span class="nd">n/d</span>'
    if key in PCT_RATIOS:
        return f"{v * 100:,.1f}%"
    if key.endswith("_days"):
        return f"{v:,.0f}"
    return f"{v:,.2f}"


def fmt_dev(key: str, v) -> str:
    if v is None:
        return "–"
    if key in PCT_RATIOS:
        return f"{v * 100:+.1f} pp"
    return f"{v:+,.1f}"


def fig_html(fig) -> str:
    if fig is None:
        return '<p class="muted">Chart omitted - insufficient comparable data.</p>'
    return '<div class="chart">' + pio.to_html(fig, full_html=False, include_plotlyjs=False,
                                               config={"displaylogo": False, "responsive": True, "displayModeBar": False}) + "</div>"


def ul(items, cls="") -> str:
    items = [i for i in (items or []) if i]
    if not items:
        return ""
    return f'<ul class="{cls}">' + "".join(f"<li>{esc(i)}</li>" for i in items) + "</ul>"


def linked(items) -> str:
    out = []
    for it in items or []:
        if isinstance(it, str):
            out.append(f"<li>{esc(it)}</li>")
            continue
        t, u = it.get("text", ""), it.get("source_url")
        src = f' <a href="{safe_url(u)}" target="_blank" rel="noopener">[source]</a>' if safe_url(u) else ""
        out.append(f"<li>{esc(t)}{src}</li>")
    return "<ul>" + "".join(out) + "</ul>" if out else '<p class="muted">None identified.</p>'


STATUS_CLS = {"Better": "good", "Worse": "bad", "At par": "par"}


def render(ident: dict, fin: dict, ds: dict, an: dict, plotly_inline: bool = True) -> str:
    t = ident["target"]
    tname = t["name"]
    ccy = ds["base_currency"]
    div, mlabel = money_unit(ccy)
    tr, crs, rows = ds["target_ratios"], ds["competitor_ratios"], ds["benchmark"]
    sv = an.get("savings", {"items": [], "totals": {"pnl": {}, "cash": {}}})
    peers = [c["name"] for c in crs]
    comp_meta = {c["name"]: c for c in ident.get("competitors", [])}

    def m(v):
        return '<span class="nd">n/d</span>' if v is None else f"{v / div:,.0f}"

    S: list[str] = []

    # ------------------------------------------------------------ 1. exec
    es = an.get("executive_summary", {})
    tot = sv["totals"]
    rev_latest = ds["latest_raw"].get("revenue")
    savings_line = ""
    if tot.get("pnl"):
        savings_line = (f'<div class="kpis">'
                        + "".join(f'<div class="kpi"><div class="kval">{tot["pnl"].get(k, 0) / div:,.0f}</div>'
                                  f'<div class="kl">{k} - {mlabel} p.a.</div></div>'
                                  for k in ("Conservative", "Moderate", "Optimistic"))
                        + (f'<div class="kpi"><div class="kval">{tot["ebitda_uplift_pct_moderate"]:.1f} pp</div>'
                           f'<div class="kl">Moderate EBITDA-margin uplift</div></div>'
                           if tot.get("ebitda_uplift_pct_moderate") is not None else "")
                        + "</div><p class='muted'>Potential, not guaranteed, savings. P&amp;L initiatives only; "
                          "one-time working-capital cash release is shown in section 8.</p>")
    S.append(f"""<section id="s1" style="--accent:#2a78d6"><h2><span>1</span>Executive summary</h2>
<p class="lead">{esc(es.get('overview'))}</p>
<h3>Overall cost competitiveness</h3><p>{esc(es.get('overall_assessment'))}</p>
<h3>Three most important insights</h3>{ul(es.get('top_insights'), 'insights')}
<h3>Key findings</h3>{ul(es.get('key_findings'))}
<h3>Estimated savings opportunity</h3>{savings_line}
<h3>At a glance</h3><div class="info-grid">
{fig_html(charts.score_gauge(rows))}{fig_html(charts.status_donut(rows))}
{fig_html(charts.revenue_donut(tr, '₹' if ccy.upper() == 'INR' else ccy + ' '))}{fig_html(charts.scenario_bars(sv, mlabel, div))}
</div></section>""")

    # ----------------------------------------------------- 2. overview
    def rev_of(name):
        for c in [tr, *crs]:
            if c["name"] == name and c["years"]:
                return c["years"][-1]["raw"].get("revenue"), c["years"][-1]["fy"]
        return None, None

    comp_rows = ""
    for c in ident.get("competitors", []):
        rv, fy = rev_of(c["name"])
        comp_rows += (f"<tr><td><b>{esc(c['name'])}</b><br><span class='muted'>{esc(c.get('ticker'))}</span></td>"
                      f"<td>{esc(c.get('headquarters'))}</td><td>{esc(c.get('primary_business'))}</td>"
                      f"<td class='num'>{m(rv)}<br><span class='muted'>{esc(fy)}</span></td>"
                      f"<td>{esc(c.get('selection_reason'))}</td><td>{esc(c.get('comparability_notes'))}</td></tr>")
    trv, tfy = rev_of(tname)
    S.append(f"""<section id="s2" style="--accent:#eb6834"><h2><span>2</span>Company and competitor overview</h2>
<div class="profile"><div><h3>{esc(tname)}</h3><p>{esc(an.get('company_profile') or t.get('description'))}</p></div>
<table class="kv"><tr><th>Headquarters</th><td>{esc(t.get('headquarters'))}</td></tr>
<tr><th>Industry</th><td>{esc(t.get('industry'))} / {esc(t.get('sub_industry'))}</td></tr>
<tr><th>Business model</th><td>{esc(t.get('business_model'))}</td></tr>
<tr><th>Products</th><td>{esc(', '.join(t.get('products') or []))}</td></tr>
<tr><th>Presence</th><td>{esc(t.get('geographic_presence'))}</td></tr>
<tr><th>Listing</th><td>{'Listed' if t.get('listed') else 'Private'} {esc(t.get('ticker'))} {esc(t.get('exchange'))}</td></tr>
<tr><th>Revenue ({esc(tfy)})</th><td>{m(trv)} {mlabel}</td></tr>
<tr><th>Website</th><td><a href="{safe_url(t.get('website'))}" target="_blank" rel="noopener">{esc(t.get('website'))}</a></td></tr></table></div>
{f'<p class="note">{esc(ident.get("ambiguity_note"))}</p>' if ident.get('ambiguity_note') else ''}
<h3>Competitor set</h3>
<table class="data"><thead><tr><th>Competitor</th><th>HQ</th><th>Primary business</th><th>Revenue ({mlabel})</th>
<th>Why selected</th><th>Comparability</th></tr></thead><tbody>{comp_rows}</tbody></table>
<h3>Selection rationale</h3><p>{esc(an.get('competitor_rationale'))}</p>
<h3>Scale and business-model comparison</h3><p>{esc(an.get('scale_and_model_comparison'))}</p></section>""")

    # ------------------------------------------------- 3. performance
    perf_keys = [("revenue", "Revenue", "raw"), ("gross_profit_used", "Gross profit", "derived"),
                 ("ebitda_used", "EBITDA", "derived"), ("ebit_used", "EBIT", "derived"),
                 ("net_profit", "Net profit", "raw")]
    yrs = tr["years"]
    head = "".join(f"<th>{esc(y['fy'])}</th>" for y in yrs)
    body = ""
    for k, label, src in perf_keys:
        body += f"<tr><td>{label}</td>" + "".join(f"<td class='num'>{m(y[src].get(k))}</td>" for y in yrs) + "</tr>"
    for k in ("gross_margin", "ebitda_margin", "ebit_margin", "net_margin"):
        body += f"<tr class='sub'><td>{RATIOS[k][0]}</td>" + "".join(
            f"<td class='num'>{fmt_ratio(k, y['ratios'].get(k))}</td>" for y in yrs) + "</tr>"
    peer_perf = ""
    for c in [tr, *crs]:
        if not c["years"]:
            continue
        y = c["years"][-1]
        peer_perf += (f"<tr{' class=tgt' if c is tr else ''}><td>{esc(c['name'])}</td><td>{esc(y['fy'])}</td>"
                      f"<td class='num'>{m(y['raw'].get('revenue'))}</td>"
                      + "".join(f"<td class='num'>{fmt_ratio(k, y['ratios'].get(k))}</td>"
                                for k in ("gross_margin", "ebitda_margin", "net_margin", "asset_turnover", "ccc_days"))
                      + "</tr>")
    S.append(f"""<section id="s3" style="--accent:#1baf7a"><h2><span>3</span>Financial performance</h2>
<p>{esc(an.get('financial_performance_commentary'))}</p>
<h3>{esc(tname)} - three-year summary ({mlabel})</h3>
<table class="data"><thead><tr><th></th>{head}</tr></thead><tbody>{body}</tbody></table>
{fig_html(charts.revenue_trend(tr, crs, mlabel, div))}
<h3>Key indicators - latest reported year</h3>
<table class="data"><thead><tr><th>Company</th><th>FY</th><th>Revenue</th><th>Gross margin</th><th>EBITDA margin</th>
<th>Net margin</th><th>Asset turnover</th><th>CCC (days)</th></tr></thead><tbody>{peer_perf}</tbody></table></section>""")

    # ----------------------------------------------- 4. cost structure
    cost_lines = ["material_cost", "cogs", "employee_cost", "manufacturing_expenses", "selling_distribution",
                  "marketing", "freight", "admin", "other_expenses", "depreciation", "finance_cost", "total_expenses"]
    body = ""
    for k in cost_lines:
        if all(y["raw"].get(k) is None for y in yrs):
            body += f"<tr class='nd-row'><td>{LINE_ITEMS[k][0]}</td><td colspan='{len(yrs)}'>Not disclosed</td></tr>"
            continue
        cells = ""
        for y in yrs:
            v, rv = y["raw"].get(k), y["raw"].get("revenue")
            pct = f" <span class='muted'>({v / rv * 100:.1f}%)</span>" if (v is not None and rv) else ""
            cells += f"<td class='num'>{m(v)}{pct}</td>"
        body += f"<tr><td>{LINE_ITEMS[k][0]}</td>{cells}</tr>"
    trend_keys = [k for k in ("cogs_pct", "employee_pct", "sd_pct", "admin_pct", "other_exp_pct",
                              "depreciation_pct", "finance_pct", "manufacturing_pct", "marketing_pct")
                  if any(y["ratios"].get(k) is not None for y in yrs)][:6]
    S.append(f"""<section id="s4" style="--accent:#eda100"><h2><span>4</span>Cost structure analysis</h2>
<p>{esc(an.get('cost_structure_commentary'))}</p>
<h3>{esc(tname)} cost lines ({mlabel}, % of revenue in brackets)</h3>
<table class="data"><thead><tr><th></th>{head}</tr></thead><tbody>{body}</tbody></table>
{fig_html(charts.composition(tr, crs))}
{fig_html(charts.trend_small_multiples(tr, crs, trend_keys)) if trend_keys else ''}</section>""")

    # ------------------------------------------------- 5. benchmarking
    bh = "".join(f"<th>{esc(p)}</th>" for p in peers)
    bb = ""
    nd_all = []
    for r in rows:
        k = r["key"]
        st = r["status"]
        if r["target"] is None and r["peer_count"] == 0:
            nd_all.append(r["label"])
            continue
        bb += (f"<tr><td title='{esc(r['formula'])}'><b>{esc(r['label'])}</b></td>"
               f"<td class='num tgt'>{fmt_ratio(k, r['target'])}</td>"
               + "".join(f"<td class='num'>{fmt_ratio(k, r['peers'].get(p))}</td>" for p in peers)
               + f"<td class='num'>{fmt_ratio(k, r['mean'])}</td><td class='num'>{fmt_ratio(k, r['median'])}</td>"
               f"<td>{esc(r['best_name'] or '–')}{(' <span class=muted>(' + fmt_ratio(k, r['best_value']) + ')</span>') if r['best_name'] else ''}</td>"
               f"<td class='num'>{fmt_dev(k, r['dev_vs_median'])}</td>"
               f"<td><span class='pill {STATUS_CLS.get(st, 'ctx')}'>{esc(st)}</span></td></tr>")
    key_bars = [r for r in rows if r["kind"] == "cost" and r["target"] is not None and r["peer_count"] >= 2][:8]
    gaps = ds["candidate_gaps"]
    S.append(f"""<section id="s5" style="--accent:#e87ba4"><h2><span>5</span>Competitive cost benchmarking</h2>
<p>{esc(an.get('benchmarking_commentary'))}</p>
<p class="muted">Latest reported year for each company. "Best" uses the nominal direction (lower cost / higher margin);
rows marked context-dependent have no automatic verdict because a lower value is not necessarily better
(e.g. marketing investment, D&amp;A reflecting owned vs leased assets, payable days). At par = within ±0.5 pp or ±5% of the median.</p>
<div class="scroll"><table class="data bench"><thead><tr><th>Metric</th><th class="tgt">{esc(tname)}</th>{bh}
<th>Mean</th><th>Median</th><th>Best</th><th>Δ vs median</th><th>Status</th></tr></thead><tbody>{bb}</tbody></table></div>
{('<p class="muted">Not disclosed by the target or any competitor: ' + esc(', '.join(nd_all)) + '. Formulas for every metric are in section 10.</p>') if nd_all else '<p class="muted">Formulas for every metric are in section 10.</p>'}
{fig_html(charts.heatmap(rows, tname))}
<h3>Cost ratio comparisons</h3><div class="grid2">{''.join(fig_html(charts.ratio_bar(r, tname)) for r in key_bars)}</div>
<h3>Cost gaps vs peer median</h3>{fig_html(charts.gap_chart(gaps, mlabel, div))}</section>""")

    # ------------------------------------------------- 6. root cause
    gl = {g["ratio_key"]: g for g in gaps}
    cards = ""
    for i, g in enumerate(an.get("gaps", []), 1):
        cg = gl.get(g.get("ratio_key"), {})
        k = g.get("ratio_key")
        stats = ""
        if cg:
            stats = (f"<div class='gstats'><div><b>{fmt_ratio(k, cg['target'])}</b><span>{esc(tname)}</span></div>"
                     f"<div><b>{fmt_ratio(k, cg['median'])}</b><span>Peer median</span></div>"
                     f"<div><b>{cg['gap_pp']:+.1f} pp</b><span>Gap</span></div>"
                     f"<div><b>{m(cg['gap_value_m'])}</b><span>{mlabel} excess</span></div>"
                     f"<div><b>{esc(', '.join(cg['better_peers']) or '–')}</b><span>Better peers</span></div></div>")
        cards += f"""<div class="card"><h3>Gap {i}: {esc(RATIOS.get(k, (k,))[0])}
<span class="pill ctx">{esc(g.get('classification'))}</span></h3>{stats}
<p>{esc(g.get('what_it_is'))}</p><p>{esc(g.get('possible_explanations'))}</p>
<div class="ev"><div><h4>Verified facts</h4>{linked(g.get('verified_facts'))}</div>
<div><h4>Evidence-supported explanations</h4>{linked(g.get('evidence_supported'))}</div>
<div><h4>Hypotheses (AI-generated, unverified)</h4>{linked(g.get('hypotheses'))}</div></div>
<p><b>Root-cause factors:</b> {esc(', '.join(g.get('root_cause_factors') or []))}</p>
<p><b>Evidence needed to validate:</b></p>{ul(g.get('validation_evidence_needed'))}</div>"""
    S.append(f"""<section id="s6" style="--accent:#6250d6"><h2><span>6</span>Root cause analysis</h2>
{cards or '<p class="muted">No material adverse cost gaps were identified versus the peer median.</p>'}</section>""")

    # --------------------------------------------- 7. recommendations
    recs = an.get("recommendations", [])
    rc = ""
    for i, r in enumerate(recs, 1):
        rc += f"""<div class="card rec"><h3>R{i}. {esc(r.get('title'))}</h3>
<div class="tags"><span class="pill ctx">Impact: {esc(r.get('impact'))}</span><span class="pill ctx">Difficulty: {esc(r.get('difficulty'))}</span>
<span class="pill ctx">{esc(r.get('horizon'))}</span><span class="pill ctx">Lever: {esc(RATIOS.get(r.get('ratio_key'), (r.get('ratio_key'),))[0])}</span></div>
<table class="kv"><tr><th>Problem</th><td>{esc(r.get('problem'))}</td></tr>
<tr><th>Proposed action</th><td>{esc(r.get('action'))}</td></tr>
<tr><th>Expected benefit</th><td>{esc(r.get('expected_benefit'))}</td></tr>
<tr><th>Complexity</th><td>{esc(r.get('implementation_complexity'))}</td></tr>
<tr><th>Timeline</th><td>{esc(r.get('timeline'))}</td></tr>
<tr><th>Risks &amp; dependencies</th><td>{esc(r.get('risks_dependencies'))}</td></tr></table></div>"""
    S.append(f"""<section id="s7" style="--accent:#2a78d6"><h2><span>7</span>Cost optimisation opportunities</h2>{rc}
{fig_html(charts.priority_matrix(recs))}</section>""")

    # ------------------------------------------------ 8. financial impact
    sb = ""
    for it in sv["items"]:
        r = recs[it["idx"]] if it["idx"] < len(recs) else {}
        sc = it["scenarios"]
        kind = {"pnl": "Annual P&amp;L", "cash": "One-time cash", "none": "Not quantified"}[it["type"]]
        rcls = '' if (it['counted'] or it['type'] == 'none') else ' class=excluded'
        sb += (f"<tr{rcls}><td>R{it['idx'] + 1}. {esc(it['title'])}</td>"
               f"<td>{esc(it['label'])}</td><td>{kind}</td><td class='num'>{m(it['current_m'])}</td>"
               f"<td class='num'>{m(it['benchmark_m'])}</td><td class='num'>{m(it['gap_m'])}</td>"
               f"<td class='num'>{it['addressable_fraction'] * 100:.0f}%</td>"
               + "".join(f"<td class='num'>{sc[k] / div:,.0f}</td>" for k in ("Conservative", "Moderate", "Optimistic"))
               + f"</tr><tr class='sub'><td colspan='10'>{esc(r.get('addressable_rationale'))} {esc(it['note'])}</td></tr>")
    tp, tc = tot.get("pnl", {}), tot.get("cash", {})
    sb += ("<tr class='total'><td colspan='7'>Total annual P&amp;L savings (de-duplicated)</td>"
           + "".join(f"<td class='num'>{tp.get(k, 0) / div:,.0f}</td>" for k in ("Conservative", "Moderate", "Optimistic")) + "</tr>")
    if any(tc.values()):
        sb += ("<tr class='total'><td colspan='7'>One-time working-capital cash release</td>"
               + "".join(f"<td class='num'>{tc.get(k, 0) / div:,.0f}</td>" for k in ("Conservative", "Moderate", "Optimistic")) + "</tr>")
    S.append(f"""<section id="s8" style="--accent:#008300"><h2><span>8</span>Financial impact</h2>
<p class="muted">All figures are <b>potential savings, not guaranteed savings</b>, in {mlabel}, based on the target's latest-year revenue of {m(rev_latest)}.</p>
<div class="scroll"><table class="data"><thead><tr><th>Initiative</th><th>Cost line</th><th>Type</th><th>Current cost</th><th>At peer median</th>
<th>Gap</th><th>Addressable</th><th>Conservative</th><th>Moderate</th><th>Optimistic</th></tr></thead><tbody>{sb}</tbody></table></div>
{fig_html(charts.waterfall(sv, mlabel, div=div))}
<h3>Key assumptions</h3><ul>
<li>Potential saving = Revenue × (Target cost ratio − Peer median ratio) × Addressable share × Gap closure.</li>
<li>Gap closure: Conservative 25%, Moderate 50%, Optimistic 75% - the benchmark is the peer <b>median</b>, never the best performer.</li>
<li>Addressable share is set per initiative to reflect product-mix, scale, geography and business-model differences (rationale under each row).</li>
<li>Initiatives targeting overlapping cost lines (e.g. COGS and material cost; S&amp;D and marketing) are counted once - the larger one; greyed rows are excluded from totals.</li>
<li>Working-capital initiatives release cash once; they are not added to annual P&amp;L savings.</li></ul></section>""")

    # ---------------------------------------------------- 9. roadmap
    rm = an.get("roadmap", {})
    S.append(f"""<section id="s9" style="--accent:#eb6834"><h2><span>9</span>Strategic roadmap</h2><div class="road">
{''.join(f'<div class="phase"><h3>{esc(p)}</h3>{ul(rm.get(p))}</div>' for p in ("0-3 months", "3-6 months", "6-12 months"))}
</div></section>""")

    # --------------------------------------------- 10. sources/method
    periods = ""
    for c in [ds["target"], *ds["competitors"]]:
        ys = c.get("years_norm") or []
        fx = "; ".join(f"{y['fy']}: avg {y['fx_avg']:.4g} / close {y['fx_close']:.4g}" for y in ys)
        periods += (f"<tr><td>{esc(c.get('name'))}</td><td>{esc(', '.join(str(y['fy']) for y in ys))}</td>"
                    f"<td>{esc(c.get('statement_basis'))}</td><td>{esc(c.get('expense_classification'))}</td>"
                    f"<td>{esc(c.get('reporting_currency'))} {esc(c.get('unit'))}</td><td>{esc(fx)}</td></tr>")
    srcs: list[tuple[str, str, str]] = []
    for s in ident.get("sources", []):
        srcs.append(("Company identification", s.get("title", ""), s.get("url", "")))
    for name, c in (fin.get("companies") or {}).items():
        for s in c.get("sources", []):
            srcs.append((name, (s.get("title") or "") + (f" - {s['covers']}" if s.get("covers") else ""), s.get("url", "")))
    for s in an.get("sources", []):
        srcs.append(("Root-cause research", s.get("title", ""), s.get("url", "")))
    seen, src_rows = set(), ""
    for scope, title, url in srcs:
        if (scope, url) in seen:
            continue
        seen.add((scope, url))
        src_rows += (f"<tr><td>{esc(scope)}</td><td>{esc(title)}</td>"
                     f"<td><a href='{safe_url(url)}' target='_blank' rel='noopener'>{esc(url[:90])}</a></td></tr>")
    notes = []
    for c in [ds["target"], *ds["competitors"]]:
        for k, v in (c.get("metric_notes") or {}).items():
            if v:
                notes.append(f"{c.get('name')} - {LINE_ITEMS.get(k, (k,))[0]}: {v}")
        notes += [f"{c.get('name')}: {f}" for f in (c.get("flags") or [])]
    deriv = sorted({n for y in tr["years"] for n in y["notes"]})
    defs = "".join(f"<tr><td>{esc(v[0])}</td><td>{esc(v[1])}</td></tr>" for v in RATIOS.values())
    errs = fin.get("errors") or {}
    S.append(f"""<section id="s10" style="--accent:#52514e"><h2><span>10</span>Sources and methodology</h2>
<h3>Reporting periods, basis and currency</h3>
<table class="data"><thead><tr><th>Company</th><th>Years used</th><th>Basis</th><th>Expense classification</th>
<th>Reported in</th><th>FX to {esc(ccy)} (avg / close)</th></tr></thead><tbody>{periods}</tbody></table>
<h3>Currency conversion</h3><p>All figures are converted to {esc(ccy)} and shown in {mlabel}. Income-statement items use the
average exchange rate for each company's financial year; balance-sheet items use the closing rate on the period-end date.
Rates were sourced by the research agent and are listed above.</p>
<h3>Financial definitions</h3><table class="data"><thead><tr><th>Metric</th><th>Formula</th></tr></thead><tbody>{defs}</tbody></table>
<ul><li>EBITDA is computed consistently as Revenue − (Total expenses − D&amp;A − Finance cost), i.e. excluding other income, where the inputs are disclosed; otherwise the reported figure is used and flagged.</li>
<li>Working-capital ratios use closing balances (opening balances are not consistently available for all peers).</li>
<li>Missing values are shown as "n/d" (not disclosed) and are never treated as zero. Peer averages use only peers that disclose the item.</li>
<li>Companies using function-of-expense reporting (cost of sales / SG&amp;A) do not disclose several nature-based lines; those ratios are not comparable and are left blank.</li></ul>
{('<p><b>Derivations applied to target:</b></p>' + ul(deriv)) if deriv else ''}
<h3>Data limitations</h3>{ul(an.get('data_limitations', []) + notes + [f'Data collection failed for {k}: {v}' for k, v in errs.items()])}
<h3>Source documents</h3><table class="data src"><thead><tr><th>Used for</th><th>Document</th><th>Link</th></tr></thead><tbody>{src_rows}</tbody></table>
</section>""")

    plotly_js = (f"<script>{get_plotlyjs()}</script>" if plotly_inline
                 else '<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>')
    nav = "".join(f'<a href="#s{i}">{i}. {n}</a>' for i, n in enumerate(
        ["Summary", "Overview", "Performance", "Cost structure", "Benchmarking", "Root causes",
         "Recommendations", "Impact", "Roadmap", "Sources"], 1))
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CostIQ - {esc(tname)} cost benchmarking</title>{plotly_js}<style>{CSS}</style></head><body>
<header><div class="brand">CostIQ</div><h1>{esc(tname)}</h1>
<p>Competitive cost intelligence &amp; optimisation report · {date.today():%d %B %Y} · Base currency {esc(ccy)}</p>
<nav>{nav}</nav></header><main>{''.join(S)}</main>
<footer>Generated by the CostIQ agent from publicly available information. Figures marked n/d were not disclosed.
AI-generated hypotheses are labelled as such and should be validated before acting. Savings are potential, not guaranteed.</footer>
</body></html>"""


CSS = """
:root{--ink:#0b0b0b;--ink2:#52514e;--muted:#8a8984;--line:#e6e5e1;--bg:#fafaf8;--card:#fff;--blue:#2a78d6;--red:#d03b3b;--green:#0a7f0a}
*{box-sizing:border-box}body{margin:0;font:14px/1.55 Inter,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;color:var(--ink);background:var(--bg)}
header{background:linear-gradient(120deg,#0d2a4a 0%,#1c5cab 55%,#6250d6 100%);color:#fff;padding:32px 40px 0}header h1{margin:4px 0;font-size:30px}header p{margin:0 0 18px;color:#c9d6e6}
.brand{font-weight:700;letter-spacing:.12em;font-size:12px;color:#86b6ef;text-transform:uppercase}
nav{display:flex;flex-wrap:wrap;gap:2px}nav a{color:#c9d6e6;text-decoration:none;padding:8px 12px;font-size:12px;border-radius:6px 6px 0 0}
nav a:hover{background:#163b63;color:#fff}
main{max-width:1180px;margin:0 auto;padding:10px 24px 40px}
section{background:var(--card);border:1px solid var(--line);border-top:4px solid var(--accent,var(--blue));border-radius:10px;padding:26px 30px;margin:22px 0;page-break-before:always}
h2{font-size:21px;margin:0 0 14px;display:flex;align-items:center;gap:12px}
h2 span{background:var(--accent,var(--blue));color:#fff;border-radius:50%;width:30px;height:30px;display:inline-flex;align-items:center;justify-content:center;font-size:14px}
h3{font-size:15px;margin:22px 0 8px}h4{font-size:13px;margin:0 0 6px;color:var(--ink2)}
.lead{font-size:16px}.muted{color:var(--muted);font-size:12px}.nd{color:var(--muted);font-style:italic}
.note{background:#fff8e6;border-left:3px solid #eda100;padding:8px 12px}
table{border-collapse:collapse;width:100%}
table.data th,table.data td{padding:7px 9px;border-bottom:1px solid var(--line);vertical-align:top;text-align:left}
table.data thead th{background:#f3f2ee;font-size:12px;color:var(--ink2);white-space:nowrap}
td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.tgt{background:#eef5fd}tr.tgt td{background:#eef5fd;font-weight:600}
tr.sub td{color:var(--ink2);font-size:12px;border-bottom:1px solid var(--line)}
tr.total td{font-weight:700;border-top:2px solid var(--ink)}tr.excluded td{color:var(--muted);text-decoration:line-through}
tr.nd-row td{color:var(--muted)}
table.kv th{text-align:left;color:var(--ink2);font-weight:600;padding:5px 12px 5px 0;width:170px;vertical-align:top}table.kv td{padding:5px 0}
.profile{display:grid;grid-template-columns:1fr 1fr;gap:28px}
.scroll{overflow-x:auto}table.bench td,table.bench th{font-size:12px;padding:6px 7px}table.bench thead th{white-space:normal}
.pill{display:inline-block;padding:2px 9px;border-radius:12px;font-size:11px;font-weight:600;white-space:nowrap;margin-left:4px}
.pill.good{background:#e3f4e3;color:var(--green)}.pill.good:before{content:"▲ "}
.pill.bad{background:#fbe7e7;color:var(--red)}.pill.bad:before{content:"▼ "}
.pill.par{background:#eef0f3;color:var(--ink2)}.pill.par:before{content:"● "}.pill.ctx{background:#f1f0ec;color:var(--ink2)}
.kpis{display:flex;gap:14px;flex-wrap:wrap}.kpi{flex:1;min-width:170px;border-radius:10px;padding:16px;color:#fff}.kpi:nth-child(1){background:linear-gradient(135deg,#86b6ef,#3987e5)}.kpi:nth-child(2){background:linear-gradient(135deg,#3987e5,#1c5cab)}.kpi:nth-child(3){background:linear-gradient(135deg,#1c5cab,#0d366b)}.kpi:nth-child(4){background:linear-gradient(135deg,#1baf7a,#0a7f55)}.kpi .kval{color:#fff}.kpi .kl{color:rgba(255,255,255,.9)}
.kval{font-size:24px;font-weight:700;color:var(--blue)}.kl{font-size:12px;color:var(--ink2)}
ul.insights li{font-size:15px;margin-bottom:6px}
.card{border:1px solid var(--line);border-radius:8px;padding:16px 20px;margin:14px 0}
.card h3{margin-top:0}.tags{margin:-4px 0 10px}.tags .pill{margin:0 6px 4px 0}
.gstats{display:flex;gap:10px;flex-wrap:wrap;margin:6px 0 10px}.gstats div{background:#f6f5f2;border-radius:6px;padding:8px 12px;min-width:110px}
.gstats b{display:block;font-size:15px}.gstats span{font-size:11px;color:var(--ink2)}
.ev{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.ev>div{background:#fafaf8;border-radius:6px;padding:10px 12px}
.ev ul{padding-left:18px;margin:0}.ev li{font-size:12.5px;margin-bottom:4px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.road{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.phase{border-top:4px solid var(--blue);background:#f6f9fd;border-radius:6px;padding:4px 16px 10px}
.chart{margin:12px 0}.info-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px 18px}.info-grid .chart{border:1px solid var(--line);border-radius:10px;padding:6px 10px;margin:6px 0}table.src td{font-size:12px;word-break:break-all}
footer{max-width:1180px;margin:0 auto 40px;padding:0 24px;color:var(--muted);font-size:12px}
a{color:var(--blue)}
@media(max-width:800px){.profile,.ev,.grid2,.road,.info-grid{grid-template-columns:1fr}section{padding:18px}}
@media print{body{background:#fff}header nav{display:none}section{border:none;margin:0}}
"""
