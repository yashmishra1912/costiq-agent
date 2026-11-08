"""Shared definitions: financial line items, ratios and their semantics."""

# Raw financial line items collected per company per financial year.
# key -> (label, definition given to the research agent)
LINE_ITEMS: dict[str, tuple[str, str]] = {
    "revenue": ("Revenue from operations", "Revenue from operations / net sales (exclude other income)."),
    "gross_profit": ("Gross profit", "As reported. If not reported, null (Python derives Revenue - COGS)."),
    "ebitda": ("EBITDA", "As reported by the company, EXCLUDING other income where possible. Null if not reported."),
    "ebit": ("EBIT", "Operating profit / EBIT as reported (before finance costs and tax). Null if not reported."),
    "net_profit": ("Net profit", "Profit after tax attributable to the period (consolidated)."),
    "cogs": ("COGS", "Cost of goods sold / cost of revenue. For nature-of-expense reporters: cost of materials consumed + purchases of stock-in-trade + changes in inventories."),
    "material_cost": ("Material cost", "Cost of materials consumed + purchases of stock-in-trade + changes in inventories (nature-of-expense reporters). Null for function-of-expense reporters that do not disclose it."),
    "employee_cost": ("Employee benefit expense", "Total employee benefits / personnel / staff costs (look in notes for function-based reporters)."),
    "manufacturing_expenses": ("Manufacturing expenses", "Power & fuel, stores & spares, conversion/processing charges, plant repairs, if disclosed. Null otherwise."),
    "selling_distribution": ("Selling & distribution expenses", "Selling & distribution / selling expenses, incl. freight and advertising if they are reported inside it."),
    "marketing": ("Advertising & marketing", "Advertising, sales promotion and marketing spend, if separately disclosed."),
    "freight": ("Freight & logistics", "Freight outward / carriage / logistics, if separately disclosed."),
    "admin": ("Administrative expenses", "General & administrative expenses if reported by function; for nature reporters use 'other expenses' only if the company labels it administrative, else null."),
    "other_expenses": ("Other expenses", "The residual 'other expenses' line for nature-of-expense reporters (total, before carving out items you listed separately)."),
    "depreciation": ("Depreciation & amortisation", "Depreciation, amortisation and impairment of PP&E / intangibles / ROU assets."),
    "finance_cost": ("Finance costs", "Interest / finance costs."),
    "total_expenses": ("Total expenses", "Total expenses as reported in the P&L (before exceptional items and tax)."),
    "inventory": ("Inventory", "Inventories at period end."),
    "receivables": ("Trade receivables", "Trade receivables at period end (current + non-current, net)."),
    "payables": ("Trade payables", "Trade payables at period end."),
    "current_assets": ("Current assets", "Total current assets."),
    "current_liabilities": ("Current liabilities", "Total current liabilities."),
    "total_assets": ("Total assets", "Total assets."),
    "employees": ("Employees (count)", "Headcount at period end (number, not money). Null if not disclosed."),
}

MONEY_ITEMS = [k for k in LINE_ITEMS if k != "employees"]

# Ratios: key -> (label, formula text, direction, kind)
#   direction: "lower" (lower is nominally better), "higher", or "context" (no automatic verdict)
#   kind: "cost" ratios become candidate cost gaps; "perf" are profitability/efficiency
RATIOS: dict[str, tuple[str, str, str, str]] = {
    "material_pct": ("Material cost / Revenue", "Material cost ÷ Revenue", "lower", "cost"),
    "employee_pct": ("Employee cost / Revenue", "Employee benefit expense ÷ Revenue", "lower", "cost"),
    "manufacturing_pct": ("Manufacturing exp. / Revenue", "Manufacturing expenses ÷ Revenue", "lower", "cost"),
    "sd_pct": ("Selling & distribution / Revenue", "Selling & distribution ÷ Revenue", "lower", "cost"),
    "marketing_pct": ("Marketing / Revenue", "Advertising & marketing ÷ Revenue", "context", "cost"),
    "freight_pct": ("Freight / Revenue", "Freight & logistics ÷ Revenue", "lower", "cost"),
    "admin_pct": ("Administrative / Revenue", "Administrative expenses ÷ Revenue", "lower", "cost"),
    "other_exp_pct": ("Other expenses / Revenue", "Other expenses ÷ Revenue", "lower", "cost"),
    "depreciation_pct": ("Depreciation / Revenue", "D&A ÷ Revenue", "context", "cost"),
    "finance_pct": ("Finance cost / Revenue", "Finance costs ÷ Revenue", "lower", "cost"),
    "opex_pct": ("Total operating exp. / Revenue", "(Revenue − EBITDA) ÷ Revenue", "lower", "total"),
    "cogs_pct": ("COGS / Revenue", "COGS ÷ Revenue", "lower", "cost"),
    "gross_margin": ("Gross profit margin", "(Revenue − COGS) ÷ Revenue", "higher", "perf"),
    "ebitda_margin": ("EBITDA margin", "EBITDA ÷ Revenue", "higher", "perf"),
    "ebit_margin": ("EBIT margin", "EBIT ÷ Revenue", "higher", "perf"),
    "net_margin": ("Net profit margin", "Net profit ÷ Revenue", "higher", "perf"),
    "rev_per_employee": ("Revenue per employee", "Revenue ÷ Employees (base-ccy millions)", "higher", "perf"),
    "inventory_turnover": ("Inventory turnover (x)", "COGS ÷ Closing inventory", "higher", "perf"),
    "receivable_days": ("Receivable days", "Closing trade receivables ÷ Revenue × 365", "lower", "perf"),
    "payable_days": ("Payable days", "Closing trade payables ÷ COGS × 365", "context", "perf"),
    "ccc_days": ("Cash conversion cycle (days)", "Inventory days + Receivable days − Payable days", "lower", "perf"),
    "asset_turnover": ("Asset turnover (x)", "Revenue ÷ Closing total assets", "higher", "perf"),
    "current_ratio": ("Current ratio (x)", "Current assets ÷ Current liabilities", "context", "perf"),
}

PCT_RATIOS = {k for k, v in RATIOS.items() if k.endswith("_pct") or k.endswith("_margin")}

# Cost-gap lines that overlap: savings within a group are never added together.
OVERLAP_GROUPS = [
    {"material_pct", "cogs_pct", "manufacturing_pct", "freight_pct"},
    {"sd_pct", "marketing_pct", "freight_pct"},
    {"admin_pct", "other_exp_pct"},
]

UNIT_TO_MILLIONS = {
    "units": 1e-6, "thousand": 1e-3, "thousands": 1e-3, "lakh": 0.1, "lakhs": 0.1,
    "million": 1.0, "millions": 1.0, "crore": 10.0, "crores": 10.0,
    "billion": 1000.0, "billions": 1000.0,
}
