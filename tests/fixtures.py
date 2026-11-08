"""FICTIONAL test data - not real companies. Used only for tests and offline rendering checks."""
import random


def company(name, rev, mat, emp, sd, other, dep, fin, ccy="INR", unit="crore", fx=1.0,
            classification="nature", disclose_sd=True, seed=0):
    rnd = random.Random(seed)
    years = []
    for i, fy in enumerate(["FY2023", "FY2024", "FY2025"]):
        g = 1 + 0.08 * (i - 2) + rnd.uniform(-0.01, 0.01)
        r = rev * g
        m, e, s, o, d, f = (r * x for x in (mat, emp, sd, other, dep, fin))
        tot = m + e + o + d + f
        years.append({
            "fy": fy, "period_end": f"{2023 + i}-03-31", "revenue": round(r, 1),
            "gross_profit": None, "ebitda": None, "ebit": None,
            "net_profit": round((r - tot) * 0.75, 1), "cogs": round(m, 1), "material_cost": round(m, 1),
            "employee_cost": round(e, 1), "manufacturing_expenses": None,
            "selling_distribution": round(s, 1) if disclose_sd else None, "marketing": None, "freight": None,
            "admin": None, "other_expenses": round(o, 1), "depreciation": round(d, 1),
            "finance_cost": round(f, 1), "total_expenses": round(tot, 1),
            "inventory": round(m * 0.2, 1), "receivables": round(r * 0.1, 1), "payables": round(m * 0.25, 1),
            "current_assets": round(r * 0.45, 1), "current_liabilities": round(r * 0.3, 1),
            "total_assets": round(r * 1.1, 1), "employees": 5000 + 500 * i,
            "fx_to_base_avg": fx, "fx_to_base_close": fx})
    return {"name": name, "statement_basis": "consolidated", "reporting_currency": ccy, "unit": unit,
            "expense_classification": classification, "years": years, "metric_notes": {},
            "comparability_flags": [], "sources": [{"title": f"{name} annual report (fictional)", "url": "https://example.com"}]}


TARGET = company("Alpha Paints (fictional)", 30000, 0.58, 0.07, 0.09, 0.17, 0.03, 0.01, seed=1)
PEERS = [
    company("Beta Coatings", 20000, 0.55, 0.06, 0.07, 0.15, 0.025, 0.004, seed=2),
    company("Gamma Colours", 9000, 0.60, 0.065, 0.08, 0.16, 0.035, 0.012, seed=3),
    company("Delta Finishes", 5000, 0.54, 0.08, 0.0, 0.18, 0.04, 0.02, disclose_sd=False, seed=4),
    company("Epsilon Global", 1500, 0.52, 0.10, 0.10, 0.14, 0.03, 0.01, ccy="USD", unit="million", fx=83.0, seed=5),
    company("Zeta Paints", 3000, 0.57, 0.06, 0.06, 0.16, 0.03, 0.005, seed=6),
]

IDENT = {
    "target": {"name": TARGET["name"], "headquarters": "Mumbai, India", "industry": "Chemicals",
               "sub_industry": "Decorative paints", "products": ["Decorative paints", "Industrial coatings"],
               "business_model": "Manufacture and dealer distribution", "geographic_presence": "India + 10 countries",
               "listed": True, "ticker": "ALPHA", "exchange": "NSE", "reporting_currency": "INR",
               "website": "https://example.com", "description": "A fictional paint company used for testing."},
    "competitors": [{"name": p["name"], "headquarters": "India", "primary_business": "Paints",
                     "selection_reason": "Direct competitor (fictional)", "comparability_notes": "n/a",
                     "ticker": "X"} for p in PEERS],
    "sources": [{"title": "Fictional", "url": "https://example.com"}],
}

ANALYSIS = {
    "executive_summary": {"overview": "Fictional overview.", "key_findings": ["Finding A", "Finding B"],
                          "overall_assessment": "Worse than median on materials.",
                          "top_insights": ["Insight 1", "Insight 2", "Insight 3"]},
    "company_profile": "Profile text.", "competitor_rationale": "Rationale.",
    "scale_and_model_comparison": "Scale text.", "financial_performance_commentary": "Perf text.",
    "cost_structure_commentary": "Cost text.", "benchmarking_commentary": "Bench text.",
    "gaps": [{"ratio_key": "material_pct", "what_it_is": "Materials", "possible_explanations": "Mix",
              "verified_facts": [{"text": "Fact", "source_url": "https://example.com"}],
              "evidence_supported": [{"text": "Evidence", "source_url": "https://example.com"}],
              "hypotheses": ["Hypothesis"], "classification": "Mixed",
              "validation_evidence_needed": ["Need X"], "root_cause_factors": ["Procurement"]}],
    "recommendations": [
        {"title": "Raw material procurement programme", "ratio_key": "material_pct", "problem": "p", "action": "a",
         "expected_benefit": "b", "addressable_fraction": 0.6, "addressable_rationale": "mix",
         "implementation_complexity": "Medium", "timeline": "6-12 months", "risks_dependencies": "r",
         "impact": "High", "difficulty": "Medium", "horizon": "Medium-term"},
        {"title": "COGS overlap test", "ratio_key": "cogs_pct", "problem": "p", "action": "a",
         "expected_benefit": "b", "addressable_fraction": 0.5, "addressable_rationale": "overlap test",
         "implementation_complexity": "Low", "timeline": "3 months", "risks_dependencies": "r",
         "impact": "Medium", "difficulty": "Medium", "horizon": "Short-term"},
        {"title": "Dealer channel cost", "ratio_key": "sd_pct", "problem": "p", "action": "a",
         "expected_benefit": "b", "addressable_fraction": 0.5, "addressable_rationale": "r",
         "implementation_complexity": "Medium", "timeline": "6 months", "risks_dependencies": "r",
         "impact": "Medium", "difficulty": "Low", "horizon": "Short-term"},
        {"title": "Receivables discipline", "ratio_key": "receivable_days", "problem": "p", "action": "a",
         "expected_benefit": "b", "addressable_fraction": 0.5, "addressable_rationale": "r",
         "implementation_complexity": "Low", "timeline": "3 months", "risks_dependencies": "r",
         "impact": "Low", "difficulty": "Low", "horizon": "Short-term"},
        {"title": "Shared services", "ratio_key": "employee_pct", "problem": "p", "action": "a",
         "expected_benefit": "b", "addressable_fraction": 0.4, "addressable_rationale": "r",
         "implementation_complexity": "High", "timeline": "12 months", "risks_dependencies": "r",
         "impact": "Medium", "difficulty": "High", "horizon": "Long-term"}],
    "roadmap": {"0-3 months": ["a"], "3-6 months": ["b"], "6-12 months": ["c"]},
    "data_limitations": ["Limitation"], "sources": [{"title": "S", "url": "https://example.com"}],
}
