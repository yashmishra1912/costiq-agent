"""CostIQ - Competitive Cost Intelligence & Optimisation Agent (Streamlit UI)."""
from __future__ import annotations

import os
import queue
import threading
import time

import pandas as pd
import streamlit as st

from costiq import metrics, pipeline, report
from costiq.schema import LINE_ITEMS

st.set_page_config(page_title="CostIQ", page_icon="📊", layout="wide")

MODELS = ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"]


def secret(name: str, default: str = "") -> str:
    try:
        return st.secrets.get(name, os.environ.get(name, default))
    except Exception:
        return os.environ.get(name, default)


# ------------------------------------------------------------------ auth
pw = secret("APP_PASSWORD")
if pw and not st.session_state.get("authed"):
    st.title("CostIQ")
    entered = st.text_input("Password", type="password")
    if entered and entered == pw:
        st.session_state.authed = True
        st.rerun()
    elif entered:
        st.error("Wrong password")
    st.stop()


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Settings")
    api_key = secret("ANTHROPIC_API_KEY") or st.text_input("Anthropic API key", type="password")
    model = st.selectbox("Model", MODELS, index=0,
                         help="Opus is the most accurate for financial extraction; Sonnet is cheaper.")
    workers = st.slider("Parallel company research", 1, 6, 2,
                        help="Higher is faster but more likely to hit API rate limits.")
    st.divider()
    runs = pipeline.Run.list_runs()
    pick = st.selectbox("Open a previous run", ["—"] + runs)
    if st.button("Open run", disabled=pick == "—"):
        st.session_state.run_id = pick
        st.rerun()
    if st.button("New analysis"):
        st.session_state.pop("run_id", None)
        st.rerun()


def run_bg(fn, *args, label: str = "Working…", **kwargs):
    """Run a stage in a background thread, streaming its log lines into the page."""
    q: queue.Queue = queue.Queue()
    box: dict = {}

    def log(msg: str) -> None:
        q.put(f"{time.strftime('%H:%M:%S')}  {msg}")

    def target():
        try:
            box["result"] = fn(*args, log=log, **kwargs)
        except Exception as e:  # surfaced below
            box["error"] = e

    th = threading.Thread(target=target, daemon=True)
    th.start()
    lines: list[str] = []
    with st.status(label, expanded=True) as status:
        area = st.empty()
        while th.is_alive() or not q.empty():
            try:
                while True:
                    lines.append(q.get_nowait())
            except queue.Empty:
                pass
            area.code("\n".join(lines[-25:]) or "starting…", language=None)
            time.sleep(0.8)
        if "error" in box:
            status.update(label=f"Failed: {box['error']}", state="error")
            raise box["error"]
        status.update(label=label.replace("…", "") + " - done", state="complete", expanded=False)
    return box.get("result")


def agent_for(log):
    return pipeline.make_agent(api_key, model, log)


# ------------------------------------------------------------ stage fns
def do_identify(run, company, hint, comps, log):
    agent = agent_for(log)
    out = pipeline.stage_identify(agent, run, company, hint, comps)
    run.save("usage_identify", agent.usage.as_dict())
    return out


def do_financials(run, ident, base, log):
    return pipeline.stage_financials(api_key, model, run, ident, base, log, workers=workers)


def do_analysis(run, ident, ds, log):
    agent = agent_for(log)
    out = pipeline.stage_analysis(agent, run, ident, ds)
    run.save("usage_analysis", agent.usage.as_dict())
    return out


# ------------------------------------------------------------------ page
st.title("CostIQ · Competitive Cost Intelligence")
st.caption("Enter a company. The agent researches it and five competitors, benchmarks 20+ cost and "
           "efficiency ratios over three years, and writes a consulting-style optimisation report.")

run = pipeline.Run(st.session_state["run_id"]) if st.session_state.get("run_id") else None

# ---- Step 1: identification
st.subheader("1 · Company & competitors")
if run is None or not run.has("identify"):
    with st.form("start"):
        c1, c2 = st.columns([2, 3])
        company = c1.text_input("Target company name", placeholder="e.g. Asian Paints")
        hint = c2.text_input("Optional hint (country, ticker, segment)", placeholder="e.g. NSE: ASIANPAINT")
        comps_txt = st.text_input("Optional: fix the five competitors (comma-separated)", "")
        go = st.form_submit_button("Identify company & competitors", type="primary")
    if go:
        if not api_key:
            st.error("Add your Anthropic API key in the sidebar (or ANTHROPIC_API_KEY secret).")
            st.stop()
        if not company.strip():
            st.error("Enter a company name.")
            st.stop()
        run = pipeline.Run.new(company)
        st.session_state.run_id = run.id
        comps = [c.strip() for c in comps_txt.split(",") if c.strip()] or None
        run_bg(do_identify, run, company.strip(), hint.strip(), comps, label="Identifying company and competitors…")
        st.rerun()
    st.stop()

ident = run.load("identify")
meta = run.load("meta") if run.has("meta") else {}
t = ident["target"]
c1, c2 = st.columns([3, 2])
with c1:
    st.markdown(f"**{t.get('name')}** · {t.get('headquarters', '')} · {t.get('industry', '')} / {t.get('sub_industry', '')}")
    st.write(t.get("description", ""))
    if ident.get("ambiguity_note"):
        st.warning(ident["ambiguity_note"])
with c2:
    st.dataframe(pd.DataFrame([{"Competitor": c.get("name"), "HQ": c.get("headquarters"),
                                "Revenue": c.get("revenue_text")} for c in ident["competitors"]]),
                 hide_index=True, width="stretch")
with st.expander("Selection rationale / change competitors"):
    for c in ident["competitors"]:
        st.markdown(f"- **{c.get('name')}** - {c.get('selection_reason', '')} _{c.get('comparability_notes', '')}_")
    new_list = st.text_input("Replace with these five (comma-separated)",
                             ", ".join(c["name"] for c in ident["competitors"]))
    if st.button("Re-run identification with this list", disabled=run.has("financials")):
        comps = [c.strip() for c in new_list.split(",") if c.strip()]
        run_bg(do_identify, run, meta.get("company", t["name"]), meta.get("hint", ""), comps,
               label="Re-identifying…")
        st.rerun()

# ---- Step 2: financials
st.subheader("2 · Financial data (3 years, consolidated)")
base_default = (t.get("reporting_currency") or "INR").upper()
fin = run.load("financials") if run.has("financials") else None
base = st.text_input("Report base currency (ISO code)", fin.get("base_currency") if fin else base_default,
                     disabled=fin is not None).upper()
need = [c["name"] for c in [t, *ident["competitors"]] if not fin or c["name"] not in fin["companies"]]
if need:
    if st.button(f"Collect financials for {len(need)} compan{'y' if len(need) == 1 else 'ies'}", type="primary"):
        run_bg(do_financials, run, ident, base, label="Collecting financial statements…")
        st.rerun()
    if fin is None:
        st.stop()
    if t["name"] not in fin["companies"]:
        st.error("Target company data is still missing - retry collection.")
        st.stop()
    st.info(f"Missing: {', '.join(need)}. You can retry, or continue with the peers collected so far.")

with st.expander("Review / correct extracted figures (values in each company's reported currency & unit)"):
    tabs = st.tabs(list(fin["companies"].keys()))
    for tab, (name, c) in zip(tabs, fin["companies"].items()):
        with tab:
            st.caption(f"{c.get('reporting_currency')} {c.get('unit')} · {c.get('statement_basis')} · "
                       f"{c.get('expense_classification')} classification")
            years = c.get("years") or []
            df = pd.DataFrame({y.get("fy"): [y.get(k) for k in [*LINE_ITEMS, "fx_to_base_avg", "fx_to_base_close"]]
                               for y in years},
                              index=[v[0] for v in LINE_ITEMS.values()] + ["FX to base (avg)", "FX to base (close)"])
            edited = st.data_editor(df, key=f"ed-{run.id}-{name}", width="stretch")
            if st.button("Save corrections", key=f"save-{name}"):
                keys = [*LINE_ITEMS, "fx_to_base_avg", "fx_to_base_close"]
                for y in years:
                    col = edited[y.get("fy")]
                    for k, v in zip(keys, col.tolist()):
                        y[k] = None if pd.isna(v) else float(v)
                c.setdefault("comparability_flags", [])
                if "Figures manually reviewed/corrected by user" not in c["comparability_flags"]:
                    c["comparability_flags"].append("Figures manually reviewed/corrected by user")
                run.save("financials", fin)
                for stale in ("dataset", "analysis"):
                    if run.has(stale):
                        run.path(stale).unlink()
                st.success("Saved. Re-run step 3 to refresh the analysis.")
            for s in c.get("sources", [])[:8]:
                st.markdown(f"- [{s.get('title') or s.get('url')}]({s.get('url')}) {s.get('covers', '')}")

# ---- Step 3: analysis + report
st.subheader("3 · Benchmarking, root causes & report")
if not run.has("analysis"):
    if st.button("Run benchmarking & write report", type="primary"):
        ds = pipeline.stage_compute(run, ident, fin)
        run_bg(do_analysis, run, ident, ds, label="Researching root causes and writing recommendations…")
        st.rerun()
    st.stop()

ds = run.load("dataset")
an = run.load("analysis")
if not run.path("report").with_suffix(".html").exists() or st.button("Rebuild report"):
    html = report.render(ident, fin, ds, an)
    (run.dir / "report.html").write_text(html, encoding="utf-8")
html = (run.dir / "report.html").read_text(encoding="utf-8")

u = [run.load(n) for n in ("usage_identify", "usage_analysis") if run.has(n)] + fin.get("usage", [])
st.caption(f"API usage this run: {sum(x.get('web_searches', 0) for x in u)} web searches · "
           f"{sum(x.get('input_tokens', 0) for x in u):,} input tokens · {sum(x.get('output_tokens', 0) for x in u):,} output tokens")
st.download_button("Download report (HTML)", html, file_name=f"CostIQ-{t['name']}.html", mime="text/html",
                   type="primary")
st.iframe(html, height=1400)
