import json
import pytest
from costiq import metrics, report
from costiq.llm import extract_json
from tests.fixtures import TARGET, PEERS, IDENT, ANALYSIS


@pytest.fixture
def ds():
    return metrics.build_dataset(TARGET, PEERS, "INR")


def test_fx_and_units(ds):
    eps = next(c for c in ds["competitor_ratios"] if c["name"] == "Epsilon Global")
    # USD 1500m * 83 = INR 124,500m
    assert eps["years"][-1]["raw"]["revenue"] == pytest.approx(1500 * 83, rel=0.02)
    tgt = ds["target_ratios"]["years"][-1]["raw"]
    assert tgt["revenue"] == pytest.approx(300000, rel=0.02)  # 30,000 crore = 300,000 m


def test_ratio_math(ds):
    r = ds["target_ratios"]["years"][-1]["ratios"]
    assert r["material_pct"] == pytest.approx(0.58, abs=1e-3)
    assert r["employee_pct"] == pytest.approx(0.07, abs=1e-3)
    # EBITDA = rev - (tot - dep - fin) = 1 - (0.58+0.07+0.17) = 0.18
    assert r["ebitda_margin"] == pytest.approx(0.18, abs=1e-3)
    assert r["ebit_margin"] == pytest.approx(0.15, abs=1e-3)
    assert r["receivable_days"] == pytest.approx(36.5, abs=0.1)


def test_missing_not_zero(ds):
    row = next(r for r in ds["benchmark"] if r["key"] == "sd_pct")
    assert row["peers"]["Delta Finishes"] is None
    assert row["peer_count"] == 4
    row = next(r for r in ds["benchmark"] if r["key"] == "manufacturing_pct")
    assert row["status"] == "Not disclosed (target)"


def test_benchmark_and_gaps(ds):
    mat = next(r for r in ds["benchmark"] if r["key"] == "material_pct")
    assert mat["median"] == pytest.approx(0.55, abs=2e-3)
    assert mat["status"] == "Worse"
    assert mat["best_name"] == "Epsilon Global"
    keys = [g["ratio_key"] for g in ds["candidate_gaps"]]
    assert "material_pct" in keys and keys[0] in ("material_pct", "cogs_pct")


def test_savings_dedupe(ds):
    sv = metrics.savings(ANALYSIS["recommendations"], ds["benchmark"], ds["latest_raw"], ds["latest_derived"])
    items = {i["ratio_key"]: i for i in sv["items"]}
    # material and cogs overlap -> only one counted
    assert items["material_pct"]["counted"] != items["cogs_pct"]["counted"]
    rev = ds["latest_raw"]["revenue"]
    m = items["material_pct"]
    if m["counted"]:
        row = next(r for r in ds["benchmark"] if r["key"] == "material_pct"); gap = row["target"] - row["median"]
        assert m["scenarios"]["Moderate"] == pytest.approx(rev * gap * 0.6 * 0.5, rel=1e-6)
    assert items["receivable_days"]["type"] in ("cash", "none")
    assert sv["totals"]["pnl"]["Optimistic"] > sv["totals"]["pnl"]["Conservative"]


def test_extract_json():
    assert extract_json('blah\n```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Here: {"a": [1,2]} done') == {"a": [1, 2]}


def test_render(ds, tmp_path):
    an = dict(ANALYSIS)
    an["savings"] = metrics.savings(an["recommendations"], ds["benchmark"], ds["latest_raw"], ds["latest_derived"])
    ds2 = json.loads(json.dumps(ds, default=str))  # as stored on disk
    html = report.render(IDENT, {"companies": {TARGET["name"]: TARGET}}, ds2, an, plotly_inline=False)
    assert "Executive summary" in html and "Sources and methodology" in html
    (tmp_path / "r.html").write_text(html)


def test_unsafe_links_dropped():
    assert report.safe_url("javascript:alert(1)") == ""
    assert report.safe_url("https://x.com/a?b=1&c=2") == "https://x.com/a?b=1&amp;c=2"
