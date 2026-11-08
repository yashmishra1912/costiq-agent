"""Orchestrates the CostIQ stages with on-disk checkpoints so a run can resume."""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Callable

from . import metrics, prompts
from .llm import Agent

RUNS_DIR = Path(__file__).resolve().parent.parent / "runs"


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60] or "run"


class Run:
    """A single analysis; every stage result is persisted as JSON in runs/<id>/."""

    def __init__(self, run_id: str):
        self.id = run_id
        self.dir = RUNS_DIR / run_id
        self.dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def new(cls, company: str) -> "Run":
        return cls(f"{datetime.now():%Y%m%d-%H%M}-{slugify(company)}")

    @staticmethod
    def list_runs() -> list[str]:
        if not RUNS_DIR.exists():
            return []
        return sorted((p.name for p in RUNS_DIR.iterdir() if p.is_dir()), reverse=True)

    def path(self, name: str) -> Path:
        return self.dir / f"{name}.json"

    def has(self, name: str) -> bool:
        return self.path(name).exists()

    def load(self, name: str):
        return json.loads(self.path(name).read_text(encoding="utf-8"))

    def save(self, name: str, data) -> None:
        self.path(name).write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str),
                                   encoding="utf-8")


def make_agent(api_key: str, model: str, log: Callable[[str], None]) -> Agent:
    return Agent(api_key=api_key, model=model, system=prompts.SYSTEM_PROMPT, log=log)


# ------------------------------------------------------------------ stages
def stage_identify(agent: Agent, run: Run, company: str, hint: str = "",
                   competitors: list[str] | None = None) -> dict:
    data = agent.run_json(prompts.identify_prompt(company, hint, competitors),
                          tools=Agent.research_tools(max_searches=12, max_fetches=6))
    data.setdefault("competitors", [])
    data["competitors"] = data["competitors"][:5]
    run.save("meta", {"company": company, "hint": hint, "model": agent.model,
                      "created": datetime.now().isoformat(timespec="seconds")})
    run.save("identify", data)
    return data


def _collect_one(api_key: str, model: str, company: dict, base: str, role: str,
                 log: Callable[[str], None]) -> tuple[dict, dict]:
    name = company.get("name") or "company"
    agent = make_agent(api_key, model, lambda m: log(f"[{name}] {m}"))
    data = agent.run_json(prompts.financials_prompt(company, base, role),
                          tools=Agent.research_tools(max_searches=12, max_fetches=8, fetch_tokens=40_000),
                          max_tokens=20_000)
    data["name"] = name
    return data, agent.usage.as_dict()


def stage_financials(api_key: str, model: str, run: Run, ident: dict, base_currency: str,
                     log: Callable[[str], None], workers: int = 2) -> dict:
    """Collect statements for target + competitors in parallel; skips companies already saved."""
    existing = run.load("financials") if run.has("financials") else {"companies": {}, "usage": []}
    jobs = [("target", ident["target"])] + [(f"competitor {i + 1}", c)
                                             for i, c in enumerate(ident["competitors"])]
    todo = [(role, c) for role, c in jobs if c.get("name") not in existing["companies"]]
    errors: dict[str, str] = {}

    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futs = {ex.submit(_collect_one, api_key, model, c, base_currency, role, log): c["name"]
                for role, c in todo}
        for fut, name in futs.items():
            try:
                data, usage = fut.result()
                existing["companies"][name] = data
                existing["usage"].append(usage)
                run.save("financials", existing)
                log(f"[{name}] financials collected")
            except Exception as e:  # keep other companies' results
                errors[name] = f"{type(e).__name__}: {e}"
                log(f"[{name}] FAILED: {errors[name]}")
    existing["base_currency"] = base_currency
    existing["errors"] = errors
    run.save("financials", existing)
    return existing


def stage_compute(run: Run, ident: dict, fin: dict) -> dict:
    base = fin.get("base_currency") or ident["target"].get("reporting_currency") or "INR"
    comps = fin["companies"]
    tname = ident["target"]["name"]
    target = comps.get(tname)
    if target is None:
        raise RuntimeError("Target company financials missing - re-run data collection")
    peers = [comps[c["name"]] for c in ident["competitors"] if c["name"] in comps]
    ds = metrics.build_dataset(target, peers, base)
    run.save("dataset", ds)
    return ds


def stage_analysis(agent: Agent, run: Run, ident: dict, ds: dict) -> dict:
    ctx = metrics.analysis_context(ds, ident)
    analysis = agent.run_json(prompts.analysis_prompt(ctx),
                              tools=Agent.research_tools(max_searches=15, max_fetches=8),
                              max_tokens=24_000)
    sv = metrics.savings(analysis.get("recommendations", []), ds["benchmark"],
                         ds["latest_raw"], ds["latest_derived"])
    analysis["savings"] = sv
    run.save("analysis", analysis)
    return analysis
