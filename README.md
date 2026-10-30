# SEC Form D Funding Tracker — New Startup Rounds

**Know which US companies raised money this week — straight from the SEC filing, whether or not they announced it.** Every company that sells shares in a Reg D private round (seed, Series A/B, SAFE, convertible note, angel) must file a **Form D** with the SEC within 15 days of the first sale. This Actor reads those official filings every business day and gives you a clean, filterable list: company, amount raised, industry, city/state, year founded, number of investors, and a direct link to the filing.

No login. No API key. No proxy. Funds, SPVs and real-estate vehicles are filtered out by default, so the list is **operating companies** you can actually sell to, recruit for, or invest alongside.

> Real example from one run (filed 2026-10-27 → 2026-10-29, tech & health, ≥ $500k): **Commure, Inc.** (Mountain View, CA) $70.1M · **TrashLab Software Inc.** (San Francisco, CA) $10.7M · **Arms Cyber Defense, Inc.** (Los Gatos, CA) $9.96M · **Septal Solutions, Inc.** (Exton, PA) $7.3M via SAFE · **Fathom Water Corp** (Kirkland, WA) $4.3M · **Swep Bio, Inc.** (Scarsdale, NY) $2.5M.

## Who it's for

| You are | What you do with it |
|---|---|
| **VC / angel / analyst** | Deal-flow and market maps: every new private round in your sector and state, with round size, security type (equity, SAFE, convertible debt) and investor count. Spot companies raising without a press release. |
| **B2B sales / agency / SaaS** | A company that just raised has new budget and a hiring plan. Reach them in the first weeks after the round. Filter by industry, state and amount to match your ICP. |
| **Recruiter / staffing BD** | Freshly funded startups hire next. Pair this list with our job-posting monitors (below) to see who raised *and* opened roles. |
| **Banking, legal, accounting, insurance** | New corporate clients that just closed a financing and need treasury, counsel, audit or D&O cover. |

## Quick start

**Free preview:** switch on **Free sample mode** → 5 operating companies from the last 3 days, not charged.

**Tech & health startups that raised ≥ $500k in the last 7 days** (this is the default form):

```json
{
  "daysBack": 7,
  "categories": ["operating_company"],
  "industries": ["Other Technology", "Computers", "Biotechnology", "Other Health Care"],
  "minAmountSold": 500000,
  "maxResults": 20
}
```

**Young California & New York companies, $1M–$20M rounds, last 30 days:**

```json
{
  "daysBack": 30,
  "states": ["CA", "NY"],
  "minAmountSold": 1000000,
  "maxAmountSold": 20000000,
  "onlyIncorporatedWithin5Years": true,
  "maxResults": 200
}
```

**Daily monitor (schedule it):** add `"onlyNewSinceLastRun": true`. The Actor remembers filings it already returned, so each scheduled run delivers only new rounds and you are **never charged twice for the same filing**. Use `stateKey` to keep separate watch lists.

More filters: `companyKeywords` / `excludeCompanyKeywords` (e.g. `["AI","Robotics"]`), `startDate` / `endDate` (up to 90 days back), `onlyNewOfferings` (skip Form D/A amendments, on by default), `categories` (switch to `pooled_fund` or `spv_or_vehicle` if you track funds instead).

## Output fields

One row per filing. Full real record: [`docs/example_output.json`](docs/example_output.json).

| Field | Meaning | Real example (TrashLab Software Inc.) |
|---|---|---|
| `company_name`, `cik` | Issuer and its SEC id | TrashLab Software Inc., 2007484 |
| `filed_date` | Date the Form D was filed | 2026-10-29 |
| `date_of_first_sale`, `days_first_sale_to_filing` | When the round started selling | 2026-06-29, 122 |
| `total_amount_sold_usd` | Money raised so far in this offering | 10,699,991 |
| `total_offering_amount_usd`, `total_remaining_usd`, `percent_sold` | Target size and progress | 10,999,989 · 299,998 · 97.3 |
| `stage_hint` | Rough bucket by amount (our estimate, not an SEC label) | series A range ($5-20M) |
| `securities_offered` | equity / debt / option / SAFE ("other: …") | ["equity"] |
| `investors_count`, `has_non_accredited_investors` | Number of investors so far | 7, false |
| `industry_group` | Issuer's self-chosen SEC industry | Other Technology |
| `issuer_city`, `issuer_state` | Principal place of business | SAN FRANCISCO, CA |
| `year_of_inc`, `incorporated_within_5_years`, `entity_type`, `jurisdiction_of_inc` | Company age and type | 2022, true, Corporation, DELAWARE |
| `revenue_range` | Self-reported revenue bucket | Decline to Disclose |
| `federal_exemptions`, `is_rule_506c_general_solicitation` | Reg D rule used | ["06b"], false |
| `uses_placement_agent`, `sales_commissions_usd`, `finders_fees_usd` | Was a broker involved | false, 0, 0 |
| `related_persons_count`, `related_person_roles` | Counts only — no names | 5, {"Director": 5, "Executive Officer": 2, "Promoter": 2} |
| `category`, `is_amendment` | operating_company / pooled_fund / spv_or_vehicle / real_estate | operating_company, false |
| `filing_url`, `xml_url`, `edgar_company_url` | Links to the original SEC documents | sec.gov links |

Exports to JSON, CSV, Excel, or via API / webhooks / Zapier / Make like any Apify dataset.

## Pricing (pay per event)

| Event | When it is charged | Price |
|---|---|---|
| `filing` | One matched Form D filing pushed to your dataset | **$0.008** (= $8 per 1,000 filings) |

That is the only charge. No start fee. Filings removed by your filters, errors, and **Free sample mode** runs are not charged. Monitor mode never re-charges a filing it already gave you. Set *Maximum cost per run* and the Actor stops cleanly at your limit.

Illustration (not a measured average): a daily monitor that returns ~20 new tech/health rounds per business day ≈ 440 filings a month ≈ **$3.52/month**.

## How is this different from Crunchbase?

| | This Actor | Crunchbase-style databases |
|---|---|---|
| Source | The official SEC Form D filing itself | A curated database built from many sources |
| Coverage | Every US Reg D offering that files a Form D, announced or not | Whatever the database has collected |
| Investor names / valuation | ❌ Not in Form D | ✅ Often |
| Price | $0.008 per filing, pay only for what you pull | Subscription |
| Delivery | Your own dataset / API / schedule | Their UI / export limits |

Use this when you want **every new US private round, fast and cheap, straight from the source**. Use Crunchbase when you need investor names or valuations.

## Data source, legality and privacy

- Source: SEC EDGAR public archives — the daily form index (`/Archives/edgar/daily-index/`) and each filing's `primary_doc.xml`. U.S. government public records.
- Follows the SEC **fair-access policy**: declared User-Agent with a contact email, default 5 requests/second (hard cap 9; SEC's limit is 10). Only `/Archives/` paths, which `robots.txt` allows.
- **No personal data in the output.** Form D lists executives, directors and promoters by name and street address; this Actor drops them and returns only role counts. No phone numbers, no street addresses.

## Limits

- Form D covers **Reg D private offerings only**. Raises without a Form D (some SAFE rounds, non-US raises, late or missing filings) won't appear.
- `stage_hint` is our amount-based estimate. `industry_group` is the issuer's own choice (many pick "Other").
- Fund/SPV detection uses the SEC industry field plus name patterns; a few edge cases can slip through.
- EDGAR publishes the daily index in the evening (US Eastern) on business days. Weekends and holidays have none.

## FAQ

**How fresh is the data?** As fresh as EDGAR: filings appear in the daily index the evening they are disseminated.

**Why didn't a company I know about show up?** It may not have filed a Form D, may have filed under a different legal name (try `companyKeywords`), or may be classed under an industry/state you filtered out.

**Can I get funds or SPVs instead of startups?** Yes: set `categories` to `["pooled_fund"]` or `["spv_or_vehicle"]`.

**Why is there a "Free sample mode" switch instead of "run with empty input"?** Apify always fills the form defaults into the input, so an empty input never reaches the Actor. The switch makes the free preview explicit.

**Can I see older filings?** Up to 90 days back per run with `startDate` / `endDate`.

## Related Actors by PaoPao Studio

- [ATS Jobs Monitor for Recruiter BD](https://apify.com/goldenrod_serrano/ats-hiring-signals) — new and closed jobs from Greenhouse, Lever, Ashby, Workable, SmartRecruiters and Recruitee, with hiring signals per company.
- [Workday Jobs Monitor for Recruiter BD](https://apify.com/goldenrod_serrano/workday-hiring-signals) — the same for companies hiring on Workday, with a country filter.

Funding (this Actor) + new job postings (above) = the two strongest "they're about to buy" signals.

## Changelog

- 1.1 — explicit **Free sample mode** (Apify fills defaults into the input, so the old "empty input = sample" never triggered on the platform); prefill trimmed to 20 results; README rewrite.
- 1.0 — first release: daily-index scan, operating-company filter, monitor mode, PPE `filing` event.

---
Made by PaoPao Studio. Questions or feature requests: use the Issues tab. Not affiliated with the U.S. SEC.
