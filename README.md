# CostIQ: Competitive Cost Intelligence Agent

Type in a company name. CostIQ researches the company and five direct competitors on the web, collects three years of consolidated financials, benchmarks 23 cost and efficiency ratios, works out likely root causes, and writes a 10-section consulting report with charts. The analysis brief it follows is in `prompts/brief.md`.

## How it works

| Stage | Who does it | Output |
|---|---|---|
| 1. Identify the company and its competitors | Claude with web search and fetch | Company profile, five competitors, selection rationale (you can override the competitors) |
| 2. Collect financials | Claude, one research agent per company, run in parallel | 24 line items × 3 years, units, FX rates and sources; you can **review and correct** every figure |
| 3. Benchmark | **Python** (deterministic) | Ratios, peer mean and median, best performer, gaps, savings scenarios |
| 4. Root causes and recommendations | Claude with web search | Facts, evidence and hypotheses kept separate; 5 recommendations |
| 5. Report | Python with Plotly | One self-contained HTML file you can download, print or save as PDF |

The arithmetic is done in Python, never by the model. Missing figures are never treated as zero. Savings are measured against the **peer median**, with conservative, moderate and optimistic scenarios closing 25%, 50% and 75% of the gap. Each recommendation also has an addressable share, and initiatives that target overlapping cost lines are counted only once.

Each stage saves its results to `runs/<id>/`. If something fails or the page reloads, you can reopen the run from the sidebar and continue where it stopped.

## Run locally

```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # then add your API key
streamlit run app.py
```

## Deploy (free) on Streamlit Community Cloud

1. Create a **private** GitHub repo and push this folder to it. The `.gitignore` keeps your secrets file out of the repo.
2. Go to https://share.streamlit.io, sign in with GitHub, and click **Create app**. Choose your repo, branch `main` and main file `app.py`.
3. Under **Advanced settings → Secrets**, paste:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   APP_PASSWORD = "your-password"
   ```
4. Click **Deploy**. You'll get a URL like `https://<name>.streamlit.app`, protected by your password.

Get an API key at https://console.anthropic.com. Web search must be enabled for your organisation there (Settings → Privacy / Tools).

**Things to know about the free host**
- Stored runs are wiped whenever the app restarts or goes to sleep, so **download each report** when it's done. If you need permanent storage, run it on Render or Railway with a persistent disk instead.
- Keep the browser tab open while a run is in progress. A full run takes about 10–25 minutes. If the tab closes, reopen the run from the sidebar and it will resume from the last completed stage.

## Cost and speed

A typical run uses around 60–100 web searches (charged at $10 per 1,000 searches) plus model tokens, mostly from the pages it reads. The app shows the exact number of searches and tokens under each report. To spend less, switch the sidebar model to **Sonnet**. If you hit rate limits, set **Parallel company research** to 1.

## Tests

```bash
python -m pytest -q
```
The tests check the ratio maths, FX and unit conversion, the "missing ≠ zero" rule, savings de-duplication and report rendering. They use fictional fixture data in `tests/fixtures.py`.

## Limitations

- The quality of the data depends on what is public. Private companies and companies that report costs by function (cost of sales and SG&A rather than materials, employees and so on) leave some ratios blank, and the report says so.
- Large annual-report PDFs can be too big for the fetch tool. The research agents fall back to exchange filings, results releases and financial data sites, and list every source in section 10. Check the key figures in step 2 before running the analysis.
