# Peak 35 Outreach Engine

A Streamlit tool that crawls a list of companies and uses GPT to generate — in bulk — either an objective company description or a personalized outreach paragraph. Built to speed up deal sourcing during a private-equity search-fund campaign.

**Live demo:** https://peak35-ai-tool-uec7m7exeocb8uhahug575.streamlit.app/

---

## Overview

Sourcing for a search fund meant reaching many SME owners, where generic templates feel impersonal and writing each message by hand doesn't scale. This tool takes a spreadsheet of target companies, reads each company's website, and produces a tailored, ready-to-use paragraph per company. The outreach paragraph follows a deliberate structure — an opening acknowledgment of the company's track record, one or two concrete distinctive points, and a close that signals genuine interest — kept short and human, not flattering or boilerplate.

## How it works

1. **Input.** Upload an Excel file with columns `Azienda` (company name) and `Sito` (website). Optionally upload a second Excel of example paragraphs (column `Paragrafo Esempio`) to steer the writing style.
2. **Targeted crawl.** For each site, the crawler prioritizes "about/company" pages (`/chi-siamo`, `/azienda`, `/about`, `/company`), favors pages about products, services and markets, and skips low-signal pages (privacy, cookie, news, careers, contact). It visits up to a configurable number of pages and stops once it has enough text.
3. **Text preparation.** Extracted text is cleaned (scripts/styles removed, content tags kept) and truncated with `tiktoken` to fit the model's context (~3,000 tokens).
4. **Generation (GPT-3.5-turbo).** Depending on the selected mode, the tool produces an objective, keyword-rich company description, a structured outreach paragraph, or both.
5. **Parallel processing.** Companies are processed concurrently with a `ThreadPoolExecutor` (configurable workers), with a live progress bar.
6. **Output.** Results are shown in-app and exported to an Excel file (`risultati_descrizioni.xlsx`) with the generated `Descrizione` and `Paragrafo Peak35` columns.

## Tech stack

- **Language:** Python
- **UI:** Streamlit
- **LLM:** OpenAI GPT-3.5-turbo
- **Scraping:** requests + BeautifulSoup4
- **Data / Excel:** pandas + openpyxl
- **Tokenization:** tiktoken
- **Concurrency:** `concurrent.futures` (thread pool)
- **Key handling:** bring-your-own-key (entered in-app, never stored)

## Project structure

```
peak35-ai-tool/
├── Peak35AITool.py        # Streamlit app: crawl → extract → GPT generation → Excel export
└── requirements.txt
```

## Setup and run

Requires Python 3.10+.

```bash
pip install -r requirements.txt
streamlit run Peak35AITool.py
```

The app uses a **bring-your-own-key** model: paste your own OpenAI API key into the field at the top of the app. The key is used only for that session, in memory — it is never stored, logged, or committed. The hosted demo works the same way, so no secret lives on the server.

> Get a key at [platform.openai.com/api-keys](https://platform.openai.com/api-keys). Never commit API keys to the repository.

## Input format

| Azienda | Sito |
|---|---|
| Example S.r.l. | https://example.com |

Optional examples file:

| Paragrafo Esempio |
|---|
| Prima di tutto, complimenti per... |

## Result

`[State the concrete outcome — e.g. "Generated personalized paragraphs for 150+ target companies, cutting outreach prep from ~X min to ~Y s each."]`

## Note

This was built for real search-fund sourcing. Before sharing publicly, make sure no real target lists, client data, or API keys are committed to the repository.

## Author

Matteo Massimo Rosetti — `https://www.linkedin.com/in/matteorosetti/`
