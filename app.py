"""CostIQ - Competitive Cost Intelligence & Optimisation Agent (Streamlit UI)."""
from __future__ import annotations

import html as _html
import os
import queue
import threading
import time

import pandas as pd
import streamlit as st

from costiq import charts, pipeline, report
from costiq.schema import LINE_ITEMS, PCT_RATIOS

st.set_page_config(page_title="CostIQ · Cost Intelligence", page_icon="📊", layout="wide",
                   initial_sidebar_state="collapsed")

MODELS = {"Opus 5.5 — most accurate": "claude-opus-5-5",
          "Sonnet 5.5 — balanced cost": "claude-sonnet-5-5",
          "Haiku 5.5 — fastest / cheapest": "claude-haiku-5-5"}

CSS = """
<style>
html, body, [class*="css"] { font-family: Inter, -apple-system, "Segoe UI", Roboto, sans-serif; }
.block-container { padding-top: 3.2rem; max-width: 1180px; }
#MainMenu, footer { visibility: hidden; }
.hero { background: radial-gradient(circle at 92% 18%, rgba(235,104,52,.55) 0, rgba(235,104,52,0) 28%),
        radial-gradient(circle at 78% 110%, rgba(27,175,122,.55) 0, rgba(27,175,122,0) 32%),
        linear-gradient(120deg, #0d2a4a 0%, #1c5cab 55%, #6250d6 100%);
        color: #fff; border-radius: 16px; padding: 30px 32px; margin: 8px 0 18px; }
.hero .brand { font-size: 12px; font-weight: 700; letter-spacing: .14em; color: #86b6ef; text-transform: uppercase; }
.hero h1 { color: #fff; font-size: 30px; margin: 4px 0 6px; padding: 0; line-height: 1.2; }
.hero p { color: #c9d6e6; margin: 0; font-size: 15px; }
.stepper { display: flex; gap: 8px; margin: 4px 0 22px; flex-wrap: wrap; }
.step { flex: 1; min-width: 150px; border-radius: 10px; padding: 10px 14px; border: 1px solid #e6e5e1;
        background: #fafaf8; font-size: 13px; color: #8a8984; }
.step b { display: block; font-size: 14px; color: #52514e; }
.step { border-top: 4px solid var(--c); }
.step.done { background: #eef7ee; border-color: #cfe8cf; border-top-color: var(--c); } .step.done b { color: #0a7f0a; }
.step.active { background: #fff; box-shadow: 0 4px 14px rgba(13,42,74,.12); border-color: var(--c); }
.step.active b { color: var(--c); }
.tiles { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 6px 0 18px; }
.tile { border-radius: 14px; padding: 16px 18px; color: #fff; }
.tile .v { font-size: 30px; font-weight: 800; line-height: 1.1; } .tile .l { font-size: 13px; opacity: .92; }
.t1 { background: linear-gradient(135deg, #3987e5, #1c5cab); } .t2 { background: linear-gradient(135deg, #f08a5d, #d95926); }
.t3 { background: linear-gradient(135deg, #2cc28c, #0f8a5f); } .t4 { background: linear-gradient(135deg, #8a7cf0, #5240c4); }
.kpi { border-radius: 14px; padding: 16px 18px; color: #fff; height: 100%; }
.kpi .v { font-size: 26px; font-weight: 800; } .kpi .l { font-size: 12.5px; opacity: .92; } .kpi .s { font-size: 12px; opacity: .85; margin-top: 2px; }
@media (max-width: 760px) { .tiles { grid-template-columns: 1fr 1fr; } }
.card { border: 1px solid #e6e5e1; border-radius: 12px; padding: 16px 18px; background: #fff; height: 100%; }
.card h4 { margin: 0 0 6px; font-size: 15px; }
.card .muted, .muted { color: #8a8984; font-size: 12.5px; }
.card p { font-size: 13.5px; margin: 4px 0 0; color: #3a3936; }
.how { border: 1px solid #e6e5e1; border-top: 4px solid var(--c); border-radius: 12px; padding: 16px 18px; background: #fff; height: 100%; }
.how .ic { font-size: 26px; margin-bottom: 4px; }
.how .n { display: inline-flex; width: 26px; height: 26px; border-radius: 50%; background: var(--c); color: #fff;
          align-items: center; justify-content: center; font-weight: 700; font-size: 13px; margin-bottom: 6px; }
.how b { display: block; margin-bottom: 4px; } .how span { font-size: 13px; color: #52514e; }
.tag { display: inline-block; background: #f1f0ec; color: #52514e; border-radius: 10px; padding: 1px 9px;
       font-size: 11.5px; font-weight: 600; margin: 2px 4px 2px 0; }
.section-title { font-size: 19px; font-weight: 700; margin: 26px 0 10px; }
div[data-testid="stMetricValue"] { font-size: 24px; }
.stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"],
div[data-testid="stFormSubmitButton"] > button { border-radius: 8px; font-weight: 600; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


def e(x) -> str:
    return _html.escape("" if x is None else str(x))


def secret(name: str, default: str = "") -> str:
    try:
        return st.secrets.get(name, os.environ.get(name, default))
    except Exception:
        return os.environ.get(name, default)


def hero(sub: str = "") -> None:
    st.markdown(f"""<div class="hero"><div class="brand">CostIQ</div>
<h1>Competitive Cost Intelligence</h1>
<p>{e(sub) or "Benchmark any company's cost structure against five competitors and get a consulting-grade optimisation report."}</p></div>""",
                unsafe_allow_html=True)


# ------------------------------------------------------------------ auth
pw = secret("APP_PASSWORD")
if pw and not st.session_state.get("authed"):
    hero("This workspace is password-protected.")
    entered = st.text_input("Password", type="password")
    if entered and entered == pw:
        st.session_state.authed = True
        st.rerun()
    elif entered:
        st.error("Wrong password")
    st.stop()

stored_key = secret("ANTHROPIC_API_KEY")


def api_key() -> str:
    return stored_key or st.session_state.get("api_key", "")


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown("### ⚙️ Settings")
    model_label = st.selectbox("Model", list(MODELS), index=0,
                               help="Opus gives the most reliable financial extraction; Sonnet roughly balances cost and quality.")
    model = MODELS[model_label]
    workers = st.slider("Parallel company research", 1, 6, 2,
                        help="Higher is faster but more likely to hit API rate limits.")
    if not stored_key and st.session_state.get("api_key"):
        st.success("API key set for this session")
        if st.button("Forget API key"):
            st.session_state.pop("api_key", None)
            st.rerun()
    st.divider()
    st.markdown("### 🗂️ Analyses")
    runs = pipeline.Run.list_runs()
    if runs:
        labels = {r: (r[14:].replace("-", " ").title() + f"  ·  {r[6:8]}/{r[4:6]} {r[9:11]}:{r[11:13]}") for r in runs}
        pick = st.selectbox("Open a previous analysis", runs, format_func=lambda r: labels[r])
        if st.button("Open", width="stretch"):
            st.session_state.run_id = pick
            st.rerun()
    else:
        st.caption("No analyses yet on this server.")
    if st.button("➕ New analysis", width="stretch", type="primary"):
        st.session_state.pop("run_id", None)
        st.rerun()
    st.caption("Saved analyses are cleared when the server restarts. Download each report.")


# ------------------------------------------------------------- helpers
def run_bg(fn, *args, label: str = "Working…", **kwargs):
    """Run a stage in a background thread, streaming its log lines into the page."""
    q: queue.Queue = queue.Queue()
    box: dict = {}

    def log(msg: str) -> None:
        q.put(f"{time.strftime('%H:%M:%S')}  {msg}")

    def target():
        try:
            box["result"] = fn(*args, log=log, **kwargs)
        except Exception as ex:  # surfaced below
            box["error"] = ex

    th = threading.Thread(target=target, daemon=True)
    th.start()
    lines: list[str] = []
    started = time.time()
    with st.status(label, expanded=True) as status:
        st.caption("Keep this tab open. Progress is saved after every step, so an interrupted run can be resumed.")
        area = st.empty()
        while th.is_alive() or not q.empty():
            try:
                while True:
                    lines.append(q.get_nowait())
            except queue.Empty:
                pass
            mins, secs = divmod(int(time.time() - started), 60)
            status.update(label=f"{label}  ({mins}:{secs:02d})")
            area.code("\n".join(lines[-18:]) or "starting…", language=None)
            time.sleep(0.8)
        if "error" in box:
            status.update(label=f"Failed: {box['error']}", state="error")
            raise box["error"]
        status.update(label=label.replace("…", "") + " — done", state="complete", expanded=False)
    return box.get("result")


STEP_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#6250d6"]


def stepper(active: int, done: set[int]) -> None:
    steps = [("🔎 Identify", "Company & 5 competitors"), ("📥 Collect data", "3 years of financials"),
             ("📊 Benchmark", "Ratios, gaps, root causes"), ("💡 Report", "Recommendations & savings")]
    html = '<div class="stepper">'
    for i, ((t, sub), col) in enumerate(zip(steps, STEP_COLORS), 1):
        cls = "done" if i in done else ("active" if i == active else "")
        mark = "✓ " if i in done else ""
        html += f'<div class="step {cls}" style="--c:{col}"><b>{mark}{t}</b>{sub}</div>'
    st.markdown(html + "</div>", unsafe_allow_html=True)


def need_key() -> bool:
    if api_key():
        return False
    st.warning("Add your Anthropic API key to run the agent.")
    return True


def key_box() -> None:
    if stored_key or st.session_state.get("api_key"):
        return
    with st.container(border=True):
        c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
        k = c1.text_input("🔑 Anthropic API key", type="password", placeholder="sk-ant-…",
                          help="Used only for this browser session; never stored on the server. "
                               "Get one at console.anthropic.com.")
        if c2.button("Use key", width="stretch") and k.strip():
            st.session_state.api_key = k.strip()
            st.rerun()
        st.caption("Your key stays in this browser session only. A full analysis typically uses 60–100 web searches plus model tokens.")


def agent_for(log):
    return pipeline.make_agent(api_key(), model, log)


def do_identify(run, company, hint, comps, log):
    agent = agent_for(log)
    out = pipeline.stage_identify(agent, run, company, hint, comps)
    run.save("usage_identify", agent.usage.as_dict())
    return out


def do_financials(run, ident, base, log):
    return pipeline.stage_financials(api_key(), model, run, ident, base, log, workers=workers)


def do_analysis(run, ident, ds, log):
    agent = agent_for(log)
    out = pipeline.stage_analysis(agent, run, ident, ds)
    run.save("usage_analysis", agent.usage.as_dict())
    return out


def fmt_r(key, v):
    if v is None:
        return "n/d"
    return f"{v * 100:.1f}%" if key in PCT_RATIOS else f"{v:,.1f}"


# ================================================================== page
run = pipeline.Run(st.session_state["run_id"]) if st.session_state.get("run_id") else None

# ---------------------------------------------------- landing / step 1
if run is None or not run.has("identify"):
    hero()
    st.markdown("""<div class="tiles">
<div class="tile t1"><div class="v">5</div><div class="l">direct competitors benchmarked</div></div>
<div class="tile t2"><div class="v">3 yrs</div><div class="l">of consolidated financials</div></div>
<div class="tile t3"><div class="v">23</div><div class="l">cost & efficiency ratios</div></div>
<div class="tile t4"><div class="v">3</div><div class="l">savings scenarios, de-duplicated</div></div></div>""",
                unsafe_allow_html=True)
    stepper(1, set())
    key_box()
    with st.form("start", border=True):
        st.markdown("**Which company should we analyse?**")
        c1, c2 = st.columns([3, 2])
        company = c1.text_input("Target company", placeholder="e.g. Asian Paints, Tata Motors, Nestlé India")
        hint = c2.text_input("Hint (optional)", placeholder="Country, ticker or segment — e.g. NSE: ASIANPAINT")
        comps_txt = st.text_input("Competitors (optional)", placeholder="Leave blank to let the agent choose five direct competitors, "
                                  "or list them comma-separated")
        go = st.form_submit_button("Start analysis →", type="primary")
    if go:
        if need_key():
            st.stop()
        if not company.strip():
            st.error("Enter a company name.")
            st.stop()
        run = pipeline.Run.new(company)
        st.session_state.run_id = run.id
        comps = [c.strip() for c in comps_txt.split(",") if c.strip()] or None
        run_bg(do_identify, run, company.strip(), hint.strip(), comps,
               label=f"Researching {company.strip()} and its competitors…")
        st.rerun()

    st.markdown('<div class="section-title">How it works</div>', unsafe_allow_html=True)
    cols = st.columns(4)
    how = [("🔎", "Identify", "Finds the company and five direct, comparable competitors with public financials."),
           ("📥", "Collect", "Reads filings for three years of consolidated statements — every figure sourced, nothing invented."),
           ("📊", "Benchmark", "Computes 23 cost & efficiency ratios in code and pinpoints where the company overspends."),
           ("💡", "Recommend", "Researches root causes and sizes five savings initiatives in three scenarios.")]
    for c, (ic, t, d), col in zip(cols, how, STEP_COLORS):
        c.markdown(f'<div class="how" style="--c:{col}"><div class="ic">{ic}</div><b>{t}</b><span>{d}</span></div>',
                   unsafe_allow_html=True)
    st.markdown('<div class="section-title">What your report includes</div>', unsafe_allow_html=True)
    g1, g2, g3, g4 = st.columns(4)
    for col, (ic, t, d) in zip((g1, g2, g3, g4), [
            ("🎯", "Competitiveness score", "One 0–100 score for how the cost base stacks up against peers"),
            ("🍩", "Where the money goes", "How each ₹100 of revenue splits across cost lines"),
            ("🌡️", "Benchmark heatmap", "Every company and metric, coloured by gap to the peer median"),
            ("🪜", "Savings waterfall", "Five sized initiatives in conservative, moderate and optimistic cases")]):
        col.markdown(f'<div class="card"><h4>{ic} {t}</h4><p>{d}</p></div>', unsafe_allow_html=True)
    st.markdown('<p class="muted" style="margin-top:18px">A full analysis takes about 10–25 minutes. '
                'Figures come from public sources and should be checked before you act on them.</p>', unsafe_allow_html=True)
    st.stop()

# ------------------------------------------------------ loaded run
ident = run.load("identify")
meta = run.load("meta") if run.has("meta") else {}
t = ident["target"]
fin = run.load("financials") if run.has("financials") else None
has_all = bool(fin) and t["name"] in fin.get("companies", {})
done = {1} | ({2} if has_all else set()) | ({3, 4} if run.has("analysis") else set())
active = 4 if run.has("analysis") else (3 if has_all else 2)

hero(f"{t.get('name')} · {t.get('industry', '')}" + (f" / {t.get('sub_industry')}" if t.get('sub_industry') else ""))
stepper(active, done)
key_box()

# ---- company + competitors
st.markdown('<div class="section-title">Company & competitor set</div>', unsafe_allow_html=True)
c1, c2 = st.columns([1.15, 2])
with c1:
    tags = "".join(f'<span class="tag">{e(p)}</span>' for p in (t.get("products") or [])[:6])
    st.markdown(f"""<div class="card"><h4>🎯 {e(t.get('name'))}</h4>
<div class="muted">{e(t.get('headquarters'))} · {'Listed ' + e(t.get('ticker')) if t.get('listed') else 'Private'} · FY ends {e(t.get('fiscal_year_end'))}</div>
<p>{e(t.get('description'))}</p><div style="margin-top:8px">{tags}</div>
<div class="muted" style="margin-top:8px">Revenue: {e(t.get('revenue_text'))}</div></div>""", unsafe_allow_html=True)
with c2:
    grid = st.columns(3)
    for i, c in enumerate(ident["competitors"]):
        with grid[i % 3]:
            st.markdown(f"""<div class="card" style="margin-bottom:10px"><h4>{e(c.get('name'))}</h4>
<div class="muted">{e(c.get('headquarters'))}</div><p>{e(c.get('revenue_text'))}</p>
<div class="muted" style="margin-top:6px">{e((c.get('selection_reason') or '')[:140])}</div></div>""", unsafe_allow_html=True)
if ident.get("ambiguity_note"):
    st.info(ident["ambiguity_note"])
if not fin:
    with st.expander("✏️ Change the competitor set"):
        new_list = st.text_input("Five competitors (comma-separated)", ", ".join(c["name"] for c in ident["competitors"]))
        if st.button("Re-run identification with this list"):
            if not need_key():
                comps = [c.strip() for c in new_list.split(",") if c.strip()]
                run_bg(do_identify, run, meta.get("company", t["name"]), meta.get("hint", ""), comps,
                       label="Re-identifying…")
                st.rerun()

# ---- step 2: financials
st.markdown('<div class="section-title">Financial data</div>', unsafe_allow_html=True)
need = [c["name"] for c in [t, *ident["competitors"]] if not fin or c["name"] not in fin["companies"]]
if need:
    with st.container(border=True):
        cc1, cc2 = st.columns([2, 1], vertical_alignment="bottom")
        base = cc1.text_input("Report currency (ISO code)",
                              (fin or {}).get("base_currency") or (t.get("reporting_currency") or "INR").upper(),
                              disabled=fin is not None, help="All companies are converted into this currency.").upper()
        if cc2.button(f"Collect financials ({len(need)} compan{'y' if len(need) == 1 else 'ies'}) →",
                      type="primary", width="stretch"):
            if not need_key():
                run_bg(do_financials, run, ident, base, label="Collecting three years of financial statements…")
                st.rerun()
        if fin and need:
            st.caption(f"Still missing: {', '.join(need)}. Retry, or continue with the peers collected so far.")
    if not has_all:
        st.stop()

companies = fin["companies"]
st.caption(f"Collected for {len(companies)} of 6 companies · base currency **{fin.get('base_currency')}** · "
           "open a company to check or correct any figure.")
with st.expander("🔍 Review & correct extracted figures"):
    tabs = st.tabs(list(companies.keys()))
    for tab, (name, c) in zip(tabs, companies.items()):
        with tab:
            st.markdown(f'<span class="tag">{e(c.get("reporting_currency"))} {e(c.get("unit"))}</span>'
                        f'<span class="tag">{e(c.get("statement_basis"))}</span>'
                        f'<span class="tag">{e(c.get("expense_classification"))} classification</span>',
                        unsafe_allow_html=True)
            years = c.get("years") or []
            keys = [*LINE_ITEMS, "fx_to_base_avg", "fx_to_base_close"]
            df = pd.DataFrame({y.get("fy"): [y.get(k) for k in keys] for y in years},
                              index=[v[0] for v in LINE_ITEMS.values()] + ["FX to base (avg)", "FX to base (close)"])
            edited = st.data_editor(df, key=f"ed-{run.id}-{name}", width="stretch")
            if st.button("Save corrections", key=f"save-{name}"):
                for y in years:
                    for k, v in zip(keys, edited[y.get("fy")].tolist()):
                        y[k] = None if pd.isna(v) else float(v)
                c.setdefault("comparability_flags", [])
                if "Figures manually reviewed/corrected by user" not in c["comparability_flags"]:
                    c["comparability_flags"].append("Figures manually reviewed/corrected by user")
                run.save("financials", fin)
                for stale in ("dataset", "analysis"):
                    if run.has(stale):
                        run.path(stale).unlink()
                if (run.dir / "report.html").exists():
                    (run.dir / "report.html").unlink()
                st.success("Saved — re-run the benchmarking to refresh the report.")
            srcs = c.get("sources", [])[:8]
            if srcs:
                st.markdown("**Sources:** " + " · ".join(f"[{s.get('title') or 'link'}]({s.get('url')})" for s in srcs))

# ---- step 3: analysis
if not run.has("analysis"):
    with st.container(border=True):
        st.markdown("**Ready to benchmark.** Ratios are computed in code; Claude then researches root causes "
                    "and writes five sized recommendations.")
        if st.button("Run benchmarking & write report →", type="primary"):
            if not need_key():
                ds = pipeline.stage_compute(run, ident, fin)
                run_bg(do_analysis, run, ident, ds, label="Researching root causes and writing recommendations…")
                st.rerun()
    st.stop()

# ---- step 4: results
ds = run.load("dataset")
an = run.load("analysis")
rp = run.dir / "report.html"
if not rp.exists():
    rp.write_text(report.render(ident, fin, ds, an), encoding="utf-8")
html = rp.read_text(encoding="utf-8")

st.markdown('<div class="section-title">Results</div>', unsafe_allow_html=True)
div, mlabel = report.money_unit(ds["base_currency"])
tot = an.get("savings", {}).get("totals", {})
bench = {r["key"]: r for r in ds["benchmark"]}
em = bench.get("ebitda_margin", {})
score = charts.competitiveness_score(ds["benchmark"])
worse = sum(1 for r in ds["benchmark"] if r["status"] == "Worse")
better = sum(1 for r in ds["benchmark"] if r["status"] == "Better")
pnl = tot.get("pnl", {})
dev = ((em["target"] - em["median"]) * 100) if em.get("target") is not None and em.get("median") is not None else None
tiles = [
    ("t1", f"{score}/100" if score is not None else "–", "Cost competitiveness score", f"{better} better · {worse} worse than peers"),
    ("t4", fmt_r("ebitda_margin", em.get("target")), "EBITDA margin, latest FY",
     f"{dev:+.1f} pp vs peer median" if dev is not None else "peer median n/a"),
    ("t3", f"{pnl.get('Moderate', 0) / div:,.0f}", f"Potential savings p.a. ({mlabel}), moderate",
     f"range {pnl.get('Conservative', 0) / div:,.0f} – {pnl.get('Optimistic', 0) / div:,.0f}"),
    ("t2", f"{tot['ebitda_uplift_pct_moderate']:.1f} pp" if tot.get("ebitda_uplift_pct_moderate") is not None else "–",
     "EBITDA-margin uplift, moderate", "potential, not guaranteed"),
]
st.markdown('<div class="tiles">' + "".join(
    f'<div class="kpi {c}"><div class="v">{e(v)}</div><div class="l">{e(l)}</div><div class="s">{e(sub)}</div></div>'
    for c, v, l, sub in tiles) + "</div>", unsafe_allow_html=True)

PCFG = {"displayModeBar": False}
sym = "₹" if ds["base_currency"].upper() == "INR" else ds["base_currency"] + " "
i1, i2 = st.columns(2)
for col, fig in ((i1, charts.score_gauge(ds["benchmark"])), (i2, charts.status_donut(ds["benchmark"])),
                 (i1, charts.revenue_donut(ds["target_ratios"], sym)),
                 (i2, charts.scenario_bars(an.get("savings", {}), mlabel, div))):
    if fig is not None:
        with col.container(border=True):
            st.plotly_chart(fig, config=PCFG, width="stretch")
gfig = charts.gap_chart(ds["candidate_gaps"], mlabel, div)
wfig = charts.waterfall(an.get("savings", {}), mlabel, div=div)
if gfig is not None or wfig is not None:
    j1, j2 = st.columns(2)
    for col, fig in ((j1, gfig), (j2, wfig)):
        if fig is not None:
            with col.container(border=True):
                st.plotly_chart(fig, config=PCFG, width="stretch")
hfig = charts.heatmap(ds["benchmark"], t["name"])
if hfig is not None:
    with st.container(border=True):
        st.plotly_chart(hfig, config=PCFG, width="stretch")

b1, b2, _ = st.columns([1.2, 1, 3])
b1.download_button("⬇️ Download full report (HTML)", html, file_name=f"CostIQ-{t['name']}.html",
                   mime="text/html", type="primary", width="stretch")
if b2.button("↻ Rebuild report", width="stretch"):
    rp.write_text(report.render(ident, fin, ds, an), encoding="utf-8")
    st.rerun()

tab_r, tab_s, tab_b = st.tabs(["📄 Full report", "💡 Recommendations", "📊 Benchmark table"])
with tab_r:
    st.iframe(html, height=1500)
with tab_s:
    items = {i["idx"]: i for i in an.get("savings", {}).get("items", [])}
    for i, r in enumerate(an.get("recommendations", [])):
        it = items.get(i, {})
        mod = it.get("scenarios", {}).get("Moderate", 0) / div if it.get("type") in ("pnl", "cash") else None
        with st.container(border=True):
            h1, h2 = st.columns([4, 1])
            h1.markdown(f"**R{i + 1}. {r.get('title')}**  \n"
                        f'<span class="tag">Impact: {e(r.get("impact"))}</span><span class="tag">Difficulty: {e(r.get("difficulty"))}</span>'
                        f'<span class="tag">{e(r.get("horizon"))}</span>', unsafe_allow_html=True)
            if mod is not None:
                h2.metric("Moderate" + (" (cash, once)" if it.get("type") == "cash" else " p.a."), f"{mod:,.0f}")
            st.markdown(f"**Problem:** {r.get('problem')}  \n**Action:** {r.get('action')}  \n"
                        f"**Timeline:** {r.get('timeline')} · **Risks:** {r.get('risks_dependencies')}")
            if it and not it.get("counted") and it.get("type") != "none":
                st.caption("Overlaps a larger initiative's cost line, so it's excluded from the savings total.")
with tab_b:
    peers = [c["name"] for c in ds["competitor_ratios"]]
    rows = []
    for r in ds["benchmark"]:
        if r["target"] is None and r["peer_count"] == 0:
            continue
        rows.append({"Metric": r["label"], t["name"]: fmt_r(r["key"], r["target"]),
                     **{p: fmt_r(r["key"], r["peers"].get(p)) for p in peers},
                     "Median": fmt_r(r["key"], r["median"]), "Best": r["best_name"] or "–", "Status": r["status"]})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", height=640)

u = [run.load(n) for n in ("usage_identify", "usage_analysis") if run.has(n)] + fin.get("usage", [])
st.caption(f"API usage for this analysis: {sum(x.get('web_searches', 0) for x in u)} web searches · "
           f"{sum(x.get('input_tokens', 0) for x in u):,} input tokens · {sum(x.get('output_tokens', 0) for x in u):,} output tokens")
