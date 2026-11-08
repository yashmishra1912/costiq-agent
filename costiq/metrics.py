"""Deterministic financial engine: normalisation, ratios, benchmarks, gaps, savings.

All money is normalised to *base-currency millions*. Percent ratios are stored as fractions.
No value is ever imputed: a ratio is None when any input is missing.
"""
from __future__ import annotations

import statistics
from typing import Any

from .schema import (LINE_ITEMS, MONEY_ITEMS, OVERLAP_GROUPS, PCT_RATIOS, RATIOS,
                     UNIT_TO_MILLIONS)

FLOW_ITEMS = {"revenue", "gross_profit", "ebitda", "ebit", "net_profit", "cogs", "material_cost",
              "employee_cost", "manufacturing_expenses", "selling_distribution", "marketing", "freight",
              "admin", "other_expenses", "depreciation", "finance_cost", "total_expenses"}
STOCK_ITEMS = set(MONEY_ITEMS) - FLOW_ITEMS
CLOSURE = {"Conservative": 0.25, "Moderate": 0.50, "Optimistic": 0.75}
CASH_RATIOS = {"receivable_days", "inventory_turnover", "ccc_days"}


def _num(v: Any) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        s = str(v).replace(",", "").strip()
        return float(s) if s and s.lower() not in {"null", "none", "n/a", "na", "not disclosed", "-"} else None
    except ValueError:
        return None


def _div(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or b == 0:
        return None
    return a / b


# --------------------------------------------------------------- normalise
def normalise(company: dict) -> dict:
    """Convert a company's raw year records into base-currency millions."""
    unit = str(company.get("unit") or "million").lower().strip()
    factor = UNIT_TO_MILLIONS.get(unit)
    flags = list(company.get("comparability_flags") or [])
    if factor is None:
        flags.append(f"Unknown unit '{unit}' - assumed millions")
        factor = 1.0
    years = []
    for y in company.get("years") or []:
        fx_avg = _num(y.get("fx_to_base_avg")) or None
        fx_close = _num(y.get("fx_to_base_close")) or fx_avg
        if fx_avg is None:
            fx_avg = fx_close = 1.0
            if str(company.get("reporting_currency", "")).upper() != str(company.get("_base", "")).upper():
                flags.append(f"{y.get('fy')}: FX rate missing - figures left unconverted")
        rec: dict[str, Any] = {"fy": y.get("fy"), "period_end": y.get("period_end"),
                               "fx_avg": fx_avg, "fx_close": fx_close}
        for k in MONEY_ITEMS:
            v = _num(y.get(k))
            if v is None:
                rec[k] = None
            else:
                rec[k] = v * factor * (fx_avg if k in FLOW_ITEMS else fx_close)
        rec["employees"] = _num(y.get("employees"))
        years.append(rec)
    years.sort(key=lambda r: str(r.get("period_end") or r.get("fy")))
    return {**company, "years_norm": years, "flags": flags}


# ------------------------------------------------------------------ ratios
def year_ratios(y: dict) -> tuple[dict[str, float | None], dict[str, float | None], list[str]]:
    """Return (ratios, derived line items, derivation notes) for one year."""
    notes: list[str] = []
    rev = y.get("revenue")
    cogs = y.get("cogs")
    if cogs is None and y.get("material_cost") is not None:
        cogs = y["material_cost"]
        notes.append("COGS proxied by material cost")
    dep, fin, tot = y.get("depreciation"), y.get("finance_cost"), y.get("total_expenses")

    # Consistent EBITDA definition: Revenue - operating expenses (excludes other income).
    if rev is not None and tot is not None and dep is not None and fin is not None:
        ebitda = rev - (tot - dep - fin)
        notes.append("EBITDA derived as Revenue − (Total expenses − D&A − Finance cost)")
    elif y.get("ebitda") is not None:
        ebitda = y["ebitda"]
        notes.append("EBITDA as reported (definition may include other income)")
    elif y.get("ebit") is not None and dep is not None:
        ebitda = y["ebit"] + dep
        notes.append("EBITDA derived as EBIT + D&A")
    else:
        ebitda = None

    if ebitda is not None and dep is not None:
        ebit = ebitda - dep
    else:
        ebit = y.get("ebit")
        if ebit is not None:
            notes.append("EBIT as reported")

    gp = (rev - cogs) if (rev is not None and cogs is not None) else y.get("gross_profit")
    inv_days = _div(y.get("inventory"), cogs)
    inv_days = inv_days * 365 if inv_days is not None else None
    rec_days = _div(y.get("receivables"), rev)
    rec_days = rec_days * 365 if rec_days is not None else None
    pay_days = _div(y.get("payables"), cogs)
    pay_days = pay_days * 365 if pay_days is not None else None
    ccc = (inv_days + rec_days - pay_days) if None not in (inv_days, rec_days, pay_days) else None

    r = {
        "material_pct": _div(y.get("material_cost"), rev),
        "employee_pct": _div(y.get("employee_cost"), rev),
        "manufacturing_pct": _div(y.get("manufacturing_expenses"), rev),
        "sd_pct": _div(y.get("selling_distribution"), rev),
        "marketing_pct": _div(y.get("marketing"), rev),
        "freight_pct": _div(y.get("freight"), rev),
        "admin_pct": _div(y.get("admin"), rev),
        "other_exp_pct": _div(y.get("other_expenses"), rev),
        "depreciation_pct": _div(dep, rev),
        "finance_pct": _div(fin, rev),
        "opex_pct": _div(rev - ebitda, rev) if (rev is not None and ebitda is not None) else None,
        "cogs_pct": _div(cogs, rev),
        "gross_margin": _div(gp, rev),
        "ebitda_margin": _div(ebitda, rev),
        "ebit_margin": _div(ebit, rev),
        "net_margin": _div(y.get("net_profit"), rev),
        "rev_per_employee": _div(rev, y.get("employees")),
        "inventory_turnover": _div(cogs, y.get("inventory")),
        "receivable_days": rec_days,
        "payable_days": pay_days,
        "ccc_days": ccc,
        "asset_turnover": _div(rev, y.get("total_assets")),
        "current_ratio": _div(y.get("current_assets"), y.get("current_liabilities")),
        "inventory_days": inv_days,
    }
    derived = {"cogs_used": cogs, "gross_profit_used": gp, "ebitda_used": ebitda, "ebit_used": ebit}
    return r, derived, notes


def company_ratios(cnorm: dict) -> dict:
    out = []
    for y in cnorm["years_norm"]:
        r, d, notes = year_ratios(y)
        out.append({"fy": y["fy"], "period_end": y.get("period_end"), "ratios": r,
                    "derived": d, "notes": notes, "raw": y})
    return {"name": cnorm.get("name"), "years": out}


# --------------------------------------------------------------- benchmark
def _tol(key: str, median: float) -> float:
    if key in PCT_RATIOS:
        return max(0.005, 0.05 * abs(median))
    if key.endswith("_days"):
        return max(5.0, 0.10 * abs(median))
    return 0.10 * abs(median)


def benchmark(target: dict, comps: list[dict]) -> list[dict]:
    """Latest-year benchmark rows. target/comps are outputs of company_ratios()."""
    def latest(c: dict) -> dict:
        return c["years"][-1]["ratios"] if c["years"] else {}

    t = latest(target)
    rows = []
    for key, (label, formula, direction, kind) in RATIOS.items():
        tv = t.get(key)
        vals = [(c["name"], latest(c).get(key)) for c in comps]
        avail = [(n, v) for n, v in vals if v is not None]
        nums = [v for _, v in avail]
        mean = statistics.fmean(nums) if nums else None
        median = statistics.median(nums) if nums else None
        best = None
        if avail and direction in ("lower", "higher"):
            best = (min if direction == "lower" else max)(avail, key=lambda x: x[1])
        if tv is None:
            status = "Not disclosed (target)"
        elif len(nums) < 2:
            status = "Insufficient peer data"
        elif direction == "context":
            status = "Context-dependent"
        else:
            dev = tv - median
            if abs(dev) <= _tol(key, median):
                status = "At par"
            else:
                worse = dev > 0 if direction == "lower" else dev < 0
                status = "Worse" if worse else "Better"
        rows.append({
            "key": key, "label": label, "formula": formula, "direction": direction, "kind": kind,
            "target": tv, "peers": dict(vals), "peer_count": len(nums),
            "mean": mean, "median": median,
            "best_name": best[0] if best else None, "best_value": best[1] if best else None,
            "dev_vs_median": (tv - median) if (tv is not None and median is not None) else None,
            "dev_vs_mean": (tv - mean) if (tv is not None and mean is not None) else None,
            "status": status,
        })
    return rows


def candidate_gaps(rows: list[dict], target_revenue: float | None) -> list[dict]:
    """Cost lines where the target spends more than the peer median, valued in money."""
    gaps = []
    if not target_revenue:
        return gaps
    for r in rows:
        if r["kind"] != "cost" or r["target"] is None or r["median"] is None or r["peer_count"] < 2:
            continue
        dev = r["target"] - r["median"]
        if dev <= _tol(r["key"], r["median"]):
            continue
        better = sorted([n for n, v in r["peers"].items() if v is not None and v < r["target"]],
                        key=lambda n: r["peers"][n])
        gaps.append({
            "ratio_key": r["key"], "label": r["label"],
            "target": r["target"], "median": r["median"], "mean": r["mean"],
            "best_name": r["best_name"], "best_value": r["best_value"],
            "gap_pp": dev * 100, "gap_value_m": dev * target_revenue,
            "better_peers": better, "direction": r["direction"],
        })
    gaps.sort(key=lambda g: g["gap_value_m"], reverse=True)
    return gaps


def working_capital_gaps(rows: list[dict], latest_raw: dict, latest_derived: dict) -> list[dict]:
    out = []
    by = {r["key"]: r for r in rows}
    rev, cogs = latest_raw.get("revenue"), latest_derived.get("cogs_used")
    r = by["receivable_days"]
    if r["target"] is not None and r["median"] is not None and rev and r["target"] - r["median"] > 5:
        out.append({"ratio_key": "receivable_days", "label": "Receivable days",
                    "target": r["target"], "median": r["median"],
                    "cash_release_m": (r["target"] - r["median"]) / 365 * rev})
    r = by["inventory_turnover"]
    if r["target"] and r["median"] and cogs and r["median"] > r["target"] * 1.1:
        inv = latest_raw.get("inventory") or 0
        out.append({"ratio_key": "inventory_turnover", "label": "Inventory turnover",
                    "target": r["target"], "median": r["median"],
                    "cash_release_m": inv - cogs / r["median"]})
    return out


# ----------------------------------------------------------------- savings
def _groups_overlap(a: str, b: str) -> bool:
    return a == b or any(a in g and b in g for g in OVERLAP_GROUPS)


def savings(recs: list[dict], rows: list[dict], latest_raw: dict, latest_derived: dict) -> dict:
    """Scenario savings per recommendation, de-duplicated across overlapping cost lines."""
    by = {r["key"]: r for r in rows}
    rev = latest_raw.get("revenue")
    items = []
    for i, rec in enumerate(recs):
        key = rec.get("ratio_key")
        r = by.get(key)
        af = _num(rec.get("addressable_fraction"))
        af = min(max(af if af is not None else 0.5, 0.0), 1.0)
        item = {"idx": i, "title": rec.get("title"), "ratio_key": key,
                "label": r["label"] if r else key, "addressable_fraction": af,
                "type": "none", "current_m": None, "benchmark_m": None,
                "gap_m": None, "scenarios": {k: 0.0 for k in CLOSURE}, "counted": False,
                "note": ""}
        if r is None or r["target"] is None or r["median"] is None or not rev:
            item["note"] = "Not quantifiable: missing target or peer data"
        elif key in CASH_RATIOS:
            wc = {w["ratio_key"]: w for w in working_capital_gaps(rows, latest_raw, latest_derived)}
            w = wc.get(key)
            if w:
                item.update(type="cash", gap_m=w["cash_release_m"],
                            scenarios={k: w["cash_release_m"] * af * c for k, c in CLOSURE.items()},
                            note="One-time working-capital cash release (not annual P&L savings)")
            else:
                item["note"] = "No adverse gap vs peer median"
        elif r["kind"] == "cost":
            gap = r["target"] - r["median"]
            item.update(current_m=r["target"] * rev, benchmark_m=r["median"] * rev)
            if gap <= 0:
                item["note"] = "Target already at/below peer median - no quantified saving"
            else:
                item.update(type="pnl", gap_m=gap * rev,
                            scenarios={k: gap * rev * af * c for k, c in CLOSURE.items()})
        else:
            item["note"] = "Ratio is not a cost line - benefit described qualitatively"
        items.append(item)

    # de-duplicate: biggest first, skip any later item overlapping a counted cost line
    counted: list[str] = []
    for it in sorted(items, key=lambda x: x["scenarios"]["Moderate"], reverse=True):
        if it["type"] == "none":
            continue
        if any(_groups_overlap(it["ratio_key"], c) for c in counted):
            it["note"] = (it["note"] + "; " if it["note"] else "") + \
                "Overlaps a larger initiative's cost line - excluded from totals to avoid double counting"
            continue
        it["counted"] = True
        counted.append(it["ratio_key"])

    totals = {"pnl": {k: sum(i["scenarios"][k] for i in items if i["counted"] and i["type"] == "pnl") for k in CLOSURE},
              "cash": {k: sum(i["scenarios"][k] for i in items if i["counted"] and i["type"] == "cash") for k in CLOSURE}}
    ebitda = latest_derived.get("ebitda_used")
    totals["ebitda_uplift_pct_moderate"] = (totals["pnl"]["Moderate"] / rev * 100) if rev else None
    totals["ebitda_base_m"] = ebitda
    return {"items": items, "totals": totals, "closure": CLOSURE}


# ------------------------------------------------------------------ driver
def build_dataset(target_raw: dict, comps_raw: list[dict], base_currency: str) -> dict:
    tn = normalise({**target_raw, "_base": base_currency})
    cns = [normalise({**c, "_base": base_currency}) for c in comps_raw]
    tr = company_ratios(tn)
    crs = [company_ratios(c) for c in cns]
    rows = benchmark(tr, crs)
    latest = tr["years"][-1] if tr["years"] else {"raw": {}, "derived": {}}
    gaps = candidate_gaps(rows, latest["raw"].get("revenue"))
    wc = working_capital_gaps(rows, latest["raw"], latest["derived"]) if tr["years"] else []
    return {"base_currency": base_currency, "target": tn, "competitors": cns,
            "target_ratios": tr, "competitor_ratios": crs, "benchmark": rows,
            "candidate_gaps": gaps, "working_capital_gaps": wc,
            "latest_raw": latest["raw"], "latest_derived": latest["derived"]}


def analysis_context(ds: dict, ident: dict) -> dict:
    """Compact view of the dataset sent to the analysis stage."""
    def fmt(k, v):
        if v is None:
            return None
        return round(v * 100, 2) if k in PCT_RATIOS else round(v, 2)

    def trend(cr):
        return [{"fy": y["fy"], **{k: fmt(k, v) for k, v in y["ratios"].items() if v is not None},
                 "revenue_m": round(y["raw"]["revenue"], 1) if y["raw"].get("revenue") else None}
                for y in cr["years"]]

    return {
        "note": "Percent ratios are in %, money in base-currency millions; latest FY per company.",
        "base_currency": ds["base_currency"],
        "target": ident.get("target"),
        "competitors": ident.get("competitors"),
        "benchmark_latest": [{"ratio_key": r["key"], "label": r["label"], "target": fmt(r["key"], r["target"]),
                              "peers": {n: fmt(r["key"], v) for n, v in r["peers"].items()},
                              "median": fmt(r["key"], r["median"]), "mean": fmt(r["key"], r["mean"]),
                              "best": r["best_name"], "status": r["status"]} for r in ds["benchmark"]],
        "target_trend": trend(ds["target_ratios"]),
        "peer_trends": {c["name"]: trend(c) for c in ds["competitor_ratios"]},
        "candidate_gaps": [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in g.items()}
                           for g in ds["candidate_gaps"]],
        "working_capital_gaps": ds["working_capital_gaps"],
        "data_flags": {c.get("name"): (c.get("flags") or []) + [f"basis: {c.get('statement_basis')}",
                       f"classification: {c.get('expense_classification')}"]
                       for c in [ds["target"], *ds["competitors"]]},
        "metric_notes": {c.get("name"): c.get("metric_notes") for c in [ds["target"], *ds["competitors"]]},
    }
