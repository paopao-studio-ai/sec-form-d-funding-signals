# SEC Form D Funding Tracker — Newly Funded Startups (Crunchbase Alternative)

Get a **daily list of US private companies that just raised money**, straight from the official **SEC EDGAR Form D** filings — the legal notice every company must file within 15 days of the first sale in a Reg D private round (seed, Series A, B, angel, SAFE/convertible, etc.).

No login, no API key, no proxy, no scraping of paywalled sites. Funds, SPVs and real-estate vehicles are filtered out by default, so you get **operating companies** you can actually sell to, recruit for, or invest alongside.

## Who uses it

- **B2B sales & agencies** — companies that just raised have budget. Reach them in the first 2 weeks.
- **Recruiters** — freshly funded startups hire next.
- **VCs, angels, analysts** — deal-flow and market maps by industry, state and round size.
- **Fintech / banking / legal / accounting** — new clients that just closed a round.

## What you get (one row per filing)

| Field | Example |
|---|---|
| `company_name` | TrashLab Software Inc. |
| `filed_date` / `date_of_first_sale` | 2026-10-29 / 2026-06-29 |
| `total_amount_sold_usd` / `total_offering_amount_usd` | 10,699,991 / 10,999,989 |
| `stage_hint` | series A range ($5-20M) — rough bucket by amount, not an official label |
| `industry_group` | Other Technology, Biotechnology, Computers, … |
| `issuer_city` / `issuer_state` | SAN FRANCISCO / CA |
| `year_of_inc` / `incorporated_within_5_years` | 2022 / true |
| `investors_count`, `securities_offered`, `federal_exemptions`, `is_rule_506c_general_solicitation` | 7, ["equity"], ["06b"], false |
| `uses_placement_agent`, `sales_commissions_usd`, `revenue_range` | false, 0, Decline to Disclose |
| `related_persons_count`, `related_person_roles` | 5, {"Director": 5, …} (counts only) |
| `filing_url`, `xml_url`, `edgar_company_url` | links to the original SEC documents |

Full sample: [`docs/example_output.json`](docs/example_output.json).

## Quick start

Run with an **empty input** to get a free sample (last 3 days, 5 rows, not charged).

Typical input — tech & health startups that raised ≥ $500k this week:

```json
{
  "daysBack": 7,
  "categories": ["operating_company"],
  "industries": ["Other Technology", "Computers", "Biotechnology", "Other Health Care"],
  "minAmountSold": 500000,
  "maxResults": 50
}
```

**Monitor mode:** set `"onlyNewSinceLastRun": true` and schedule the Actor daily. It remembers which filings it already returned (named key-value store), so each scheduled run gives you only new rounds and you are never charged twice for the same filing.

Other filters: `states` (e.g. `["CA","NY","TX"]`), `maxAmountSold`, `onlyIncorporatedWithin5Years`, `companyKeywords` / `excludeCompanyKeywords`, `startDate` / `endDate` (up to 90 days back), `onlyNewOfferings` (skip Form D/A amendments; default on).

## Pricing (pay per event)

| Event | When | Price |
|---|---|---|
| `filing` | one matched Form D filing pushed to the dataset | **$0.008** (= $8 per 1,000) |
| Actor start | Apify's standard start event | Apify default |

Skipped filings, funds you filtered out, errors and the empty-input sample are **not charged**. Set *Maximum cost per run* in Apify and the Actor stops cleanly when it is reached.

## Data source, legality and privacy

- Source: SEC EDGAR public archives — daily form index (`/Archives/edgar/daily-index/`) and each filing's `primary_doc.xml`. US government public records.
- Follows the SEC **fair-access policy**: declared User-Agent with contact email, default 5 requests/second (hard cap 9; SEC limit is 10). Only `/Archives/` paths, which `robots.txt` allows; no full-text-search or `/cgi-bin` endpoints.
- **No personal data in the output**: Form D lists executives, directors and promoters by name and street address — this Actor deliberately drops them and returns only role counts. No phone numbers, no street addresses.
- EDGAR publishes the daily index in the evening (US Eastern) on business days; weekends/holidays have no index.

## Limits — read before buying

- Form D covers **Reg D private offerings only**. Rounds raised without a Form D (some SAFE rounds, non-US raises, companies that file late or not at all) won't appear. It is not a full Crunchbase replacement: no investor names, no valuation.
- `stage_hint` is an estimate from the amount sold, not the company's own label.
- `industry_group` is the issuer's self-selected SEC category (many pick "Other").
- Fund/SPV detection uses the SEC industry field plus name patterns; a few edge cases can slip through either way.

## FAQ

**Is this a Crunchbase alternative?** For "which US companies just raised a private round", yes — it reads the official SEC filing directly instead of a news-based database. For investor names or valuations, no.

**How fresh?** Same day EDGAR publishes the index (evening US Eastern).

**Can I get funds instead?** Set `categories` to `["pooled_fund"]` or `["spv_or_vehicle"]`.

## Changelog

- 1.0 — first release: daily-index scan, operating-company filter, monitor mode, PPE `filing` event.

---
Made by PaoPao Studio. Issues and feature requests: use the Issues tab. Not affiliated with the U.S. SEC.
