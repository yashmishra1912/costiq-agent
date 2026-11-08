"""Stage prompts. The full analyst brief (prompts/brief.md) is the system prompt for every stage."""
from __future__ import annotations

import json
from pathlib import Path

from .schema import LINE_ITEMS

BRIEF = (Path(__file__).resolve().parent.parent / "prompts" / "brief.md").read_text(encoding="utf-8")

PIPELINE_NOTE = """

# PIPELINE OPERATING NOTE (overrides formatting instructions above)
You are running as ONE STAGE of an automated pipeline. Python code computes every ratio,
average, gap and savings figure deterministically and renders the final report and charts.
Therefore, in each stage:
- Do only what the stage instructions ask.
- Your final answer must be a single JSON value inside one ```json code fence, with nothing after it.
- Never fabricate numbers or sources. Use null for anything not disclosed. Every number must come from a source you actually read.
- Keep research efficient: prefer pages that summarise multi-year statements (exchange filings, company IR results pages,
  results press releases, investor presentations, reputable financial data sites) over fetching 300-page annual-report PDFs.
"""

SYSTEM_PROMPT = BRIEF + PIPELINE_NOTE


def identify_prompt(company: str, hint: str = "", competitor_override: list[str] | None = None) -> str:
    override = ""
    if competitor_override:
        override = ("\nThe user has specified the competitor set; use exactly these five (resolve each to the right legal entity): "
                    + ", ".join(competitor_override) + "\n")
    return f"""STAGE 1 - COMPANY & COMPETITOR IDENTIFICATION (brief sections 2 and 3)

Target company: {company}
{('User hint: ' + hint) if hint else ''}{override}
Research the target and select five direct competitors, prioritising ones with public financial statements.
Return JSON exactly in this shape:
```json
{{
  "target": {{
    "name": "", "legal_name": "", "website": "", "ticker": "", "exchange": "",
    "headquarters": "", "country": "", "industry": "", "sub_industry": "",
    "products": [""], "business_model": "", "geographic_presence": "",
    "listed": true, "latest_fy": "FY2025", "fiscal_year_end": "March",
    "reporting_currency": "INR", "revenue_text": "e.g. ₹12,345 crore (FY2025)",
    "description": "3-4 sentence profile"
  }},
  "ambiguity_note": null,
  "competitors": [
    {{"name": "", "legal_name": "", "ticker": "", "headquarters": "", "primary_business": "",
      "reporting_currency": "", "revenue_text": "", "listed": true,
      "selection_reason": "", "comparability_notes": "scale / model / geography differences"}}
  ],
  "sources": [{{"title": "", "url": ""}}]
}}
```
"""


def financials_prompt(company: dict, base_currency: str, role: str) -> str:
    items = "\n".join(f"- {k}: {desc}" for k, (_, desc) in LINE_ITEMS.items())
    template = {k: None for k in LINE_ITEMS}
    year_tpl = {"fy": "FY2025", "period_end": "2025-03-31", **template,
                "fx_to_base_avg": 1.0, "fx_to_base_close": 1.0}
    out = {
        "name": company.get("name"), "statement_basis": "consolidated",
        "reporting_currency": "INR", "unit": "crore",
        "expense_classification": "nature | function | mixed",
        "years": [year_tpl],
        "metric_notes": {"selling_distribution": "e.g. included within other expenses; not separately disclosed"},
        "comparability_flags": ["e.g. FY ends December; large financial-services segment included"],
        "sources": [{"title": "", "url": "", "covers": "FY2023-FY2025 P&L"}],
    }
    return f"""STAGE 2 - FINANCIAL DATA COLLECTION (brief section 4) for the {role}

Company: {company.get('legal_name') or company.get('name')} (ticker: {company.get('ticker') or 'n/a'}, HQ: {company.get('headquarters') or 'n/a'})
Collect the latest THREE completed financial years of CONSOLIDATED figures (standalone only if consolidated is unavailable - then set statement_basis accordingly).

Line items (all monetary values in ONE unit for the whole company, stated in "unit": one of thousand, lakh, million, crore, billion):
{items}

Rules:
- Use null for "Not Disclosed". Never treat missing as zero and never back-solve a value you did not read, except simple sums the filing itself presents (e.g. materials + purchases + inventory change).
- Note in metric_notes where a line is embedded in another line or defined differently.
- `expense_classification`: "nature" if the P&L lists expenses by type (materials, employee, D&A, other), "function" if by cost of sales / SG&A.
- Currency conversion: base currency for the report is {base_currency}. For each year give fx_to_base_avg (average rate for that financial year: 1 unit of reporting currency = X {base_currency}) and fx_to_base_close (rate on period_end). Use 1.0 if reporting currency is {base_currency}. Cite the FX source in sources.
- `fy` labels: use the company's own fiscal-year label (e.g. "FY2025" for year ending Mar-2025, "CY2024" for Dec-2024).
- Order years oldest to newest.

Return JSON exactly in this shape:
```json
{json.dumps(out, indent=2, ensure_ascii=False)}
```
"""


def analysis_prompt(context: dict) -> str:
    shape = {
        "executive_summary": {
            "overview": "", "key_findings": [""], "overall_assessment": "",
            "top_insights": ["", "", ""]},
        "company_profile": "",
        "competitor_rationale": "",
        "scale_and_model_comparison": "",
        "financial_performance_commentary": "",
        "cost_structure_commentary": "",
        "benchmarking_commentary": "",
        "gaps": [{
            "ratio_key": "", "what_it_is": "",
            "possible_explanations": "",
            "verified_facts": [{"text": "", "source_url": ""}],
            "evidence_supported": [{"text": "", "source_url": ""}],
            "hypotheses": [""],
            "classification": "Potential inefficiency | Strategic choice | Mixed | Inconclusive",
            "validation_evidence_needed": [""],
            "root_cause_factors": ["e.g. economies of scale, product mix, outsourcing"]}],
        "recommendations": [{
            "title": "", "ratio_key": "", "problem": "", "action": "",
            "expected_benefit": "",
            "addressable_fraction": 0.6,
            "addressable_rationale": "share of the gap to the competitor median that is realistically addressable given mix/scale/model",
            "implementation_complexity": "", "timeline": "",
            "risks_dependencies": "",
            "impact": "High|Medium|Low", "difficulty": "High|Medium|Low",
            "horizon": "Short-term|Medium-term|Long-term"}],
        "roadmap": {"0-3 months": [""], "3-6 months": [""], "6-12 months": [""]},
        "data_limitations": [""],
        "sources": [{"title": "", "url": ""}],
    }
    return f"""STAGE 3 - ROOT CAUSE ANALYSIS, RECOMMENDATIONS & NARRATIVE (brief sections 7-11, 14)

Below is the computed dataset (all ratios computed by Python from the collected statements; base currency {context.get('base_currency')}, money in millions).
Do NOT recompute or restate different numbers; reference these figures. Research root causes on the web (MD&A, investor
presentations, competitor announcements, industry reports) for the candidate gaps.

DATA:
```json
{json.dumps(context, indent=1, ensure_ascii=False, default=str)}
```

Instructions:
- `gaps`: choose the (up to) five most material and controllable gaps from `candidate_gaps` (use their ratio_key). If fewer than five are real, return fewer and say so in data_limitations.
- Clearly separate verified facts (with source_url), evidence-supported explanations (with source_url) and hypotheses.
- `recommendations`: exactly five, specific to this company's business model; each tied to ONE ratio_key from candidate_gaps
  (or a perf ratio like receivable_days for working-capital ideas). Prefer distinct ratio_keys to avoid double counting.
  addressable_fraction is 0-1 and must reflect mix/scale/geography differences - do not assume the company can match the best competitor.
- Use plain consulting language; no generic advice like "reduce costs".
- Answer the five management questions in executive_summary.key_findings.

Return JSON exactly in this shape:
```json
{json.dumps(shape, indent=2)}
```
"""
