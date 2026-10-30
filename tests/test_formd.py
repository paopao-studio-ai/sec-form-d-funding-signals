import json
from datetime import date
from pathlib import Path

from src import formd

FX = Path(__file__).parent / "fixtures"
ROW = {"form_type": "D", "company_name": "CVAT.ai Corp", "cik": "2157596", "filed_date": "2026-10-28",
       "accession_number": "0002157596-26-000001", "path": "edgar/data/2157596/0002157596-26-000001.txt"}


def test_date_range_business_days_only():
    days = formd.date_range(date(2026, 10, 23), date(2026, 10, 27))  # Fri..Tue
    assert [d.isoformat() for d in days] == ["2026-10-23", "2026-10-26", "2026-10-27"]


def test_resolve_dates_days_back_and_cap():
    t = date(2026, 10, 30)
    assert formd.resolve_dates({"daysBack": 2}, t)[-1] == t
    assert len(formd.resolve_dates({"daysBack": 9999}, t)) <= 66  # capped at 90 calendar days
    assert formd.resolve_dates({"startDate": "2026-10-26", "endDate": "2026-12-31"}, t)[-1] == t


def test_index_url():
    assert formd.index_url(date(2026, 10, 28)) == \
        "https://www.sec.gov/Archives/edgar/daily-index/2026/QTR4/form.20261028.idx"


def test_parse_index_real_file():
    txt = (FX / "form.20261028.idx").read_text()
    rows = formd.parse_index(txt)
    assert len(rows) == 3 and all(r["form_type"] == "D" for r in rows)
    assert rows[1] == {**rows[1], "company_name": "4PG Trailer Fund LLC", "cik": "2160312",
                       "filed_date": "2026-10-28", "accession_number": "0002160312-26-000001"}
    assert len(formd.parse_index(txt, include_amendments=True)) == 4


def test_primary_doc_url():
    assert formd.primary_doc_url(ROW) == \
        "https://www.sec.gov/Archives/edgar/data/2157596/000215759626000001/primary_doc.xml"


def test_parse_operating_company():
    rec = formd.parse_form_d((FX / "operating.xml").read_text(), ROW)
    assert rec["company_name"] == "CVAT.ai Corp"
    assert rec["category"] == "operating_company" and rec["is_operating_company"] is True
    assert rec["industry_group"] == "Other Technology"
    assert rec["total_amount_sold_usd"] == 2499998 and rec["total_offering_amount_usd"] == 5499997
    assert rec["date_of_first_sale"] == "2026-10-20" and rec["days_first_sale_to_filing"] == 8
    assert rec["stage_hint"].startswith("seed")
    assert rec["is_amendment"] is False


def test_output_has_no_personal_data():
    rec = formd.parse_form_d((FX / "operating.xml").read_text(), ROW)
    blob = json.dumps(rec).lower()
    assert "redacted" not in blob and "0000000000" not in blob  # names/streets/phones never copied
    for k in rec:
        assert not any(x in k for x in ("first_name", "last_name", "street", "phone", "signer"))
    assert isinstance(rec["related_persons_count"], int)


def test_pooled_and_spv_classification():
    row = {**ROW, "company_name": "125 Ventures SPV Women's Pro B-Ball League a series of Allocations 2026 Master, LLC"}
    rec = formd.parse_form_d((FX / "pooled.xml").read_text(), row)
    assert rec["category"] in ("pooled_fund", "spv_or_vehicle")
    assert formd.classify("Acme Robotics, Inc.", "Other Technology") == "operating_company"
    assert formd.classify("Foo Co-Invest LP", "Other") == "spv_or_vehicle"
    assert formd.classify("Bar Capital LLC", "Investing") == "spv_or_vehicle"
    assert formd.classify("Main St REIT", "REITS and Finance") == "real_estate"
    assert formd.classify("Any Fund", "Pooled Investment Fund") == "pooled_fund"


def test_prefilter_keywords_word_boundary_and_spv_skip():
    rows = [{"company_name": n} for n in ["CVAT.ai Corp", "Retail Brands Inc", "Alpha SPV I LLC", "Aino Health"]]
    names = [r["company_name"] for r in formd.prefilter_index(rows, {"companyKeywords": ["AI"]})]
    assert names == ["CVAT.ai Corp"]
    names = [r["company_name"] for r in formd.prefilter_index(rows, {})]
    assert "Alpha SPV I LLC" not in names and "Retail Brands Inc" in names
    names = [r["company_name"] for r in formd.prefilter_index(rows, {"categories": ["spv_or_vehicle"]})]
    assert "Alpha SPV I LLC" in names


def test_matches_filters():
    rec = formd.parse_form_d((FX / "operating.xml").read_text(), ROW)
    assert formd.matches(rec, {})
    assert formd.matches(rec, {"industries": ["other technology"], "minAmountSold": 1_000_000})
    assert not formd.matches(rec, {"minAmountSold": 3_000_000})
    assert not formd.matches(rec, {"maxAmountSold": 1_000_000})
    assert not formd.matches(rec, {"categories": ["pooled_fund"]})
    assert not formd.matches(rec, {"industries": ["Biotechnology"]})
    st = rec["issuer_state"]
    assert formd.matches(rec, {"states": [st.lower()]}) and not formd.matches(rec, {"states": ["ZZ"]})
    assert not formd.matches({**rec, "is_amendment": True}, {})
    assert formd.matches({**rec, "is_amendment": True}, {"onlyNewOfferings": False})


def test_rate_limiter_caps_at_9_per_second():
    assert formd.RateLimiter(50).interval >= 1 / 9.0 - 1e-9


def test_schemas_are_consistent():
    root = Path(__file__).parent.parent / ".actor"
    inp = json.loads((root / "input_schema.json").read_text())["properties"]
    used = {"sampleMode", "daysBack", "startDate", "endDate", "categories", "industries", "states", "minAmountSold",
            "maxAmountSold", "onlyIncorporatedWithin5Years", "onlyNewOfferings", "companyKeywords",
            "excludeCompanyKeywords", "onlyNewSinceLastRun", "stateKey", "maxResults", "maxFilingsToScan",
            "requestsPerSecond", "userAgent", "changeTracking", "signalScoring", "scoreIndustries"}
    assert used == set(inp)
    rec = formd.parse_form_d((FX / "operating.xml").read_text(), ROW)
    view = json.loads((root / "dataset_schema.json").read_text())["views"]["filings"]["transformation"]["fields"]
    assert set(view) <= set(rec), set(view) - set(rec)
    rec.update(formd.score_filing(rec, 0))
    formd.apply_tracking([rec], {}, "2026-10-30T00:00:00Z")
    sig = json.loads((root / "dataset_schema.json").read_text())["views"]["signals"]["transformation"]["fields"]
    assert set(sig) <= set(rec), set(sig) - set(rec)


def test_long_keyword_is_prefix_match():
    rows = [{"company_name": "Accufy Biotech Inc"}, {"company_name": "Symbiotic Labs"}]
    assert [r["company_name"] for r in formd.prefilter_index(rows, {"companyKeywords": ["bio"]})] == ["Accufy Biotech Inc"]


# --- run mode: the platform never sends an empty input, so sample must be explicit -------------
SCHEMA = json.loads((Path(__file__).parent.parent / ".actor" / "input_schema.json").read_text())["properties"]


def _platform_input(user: dict) -> dict:
    """What Apify actually passes: schema defaults filled in for every missing field."""
    return {**{k: v["default"] for k, v in SCHEMA.items() if "default" in v}, **user}


def _console_prefill() -> dict:
    return _platform_input({k: v["prefill"] for k, v in SCHEMA.items() if "prefill" in v})


def test_console_prefill_is_a_paid_run_not_sample():
    inp, sample = formd.plan_run(_console_prefill())
    assert sample is False and inp["maxResults"] == SCHEMA["maxResults"]["prefill"]
    assert "sampleMode" not in inp


def test_api_call_with_only_defaults_is_paid():
    inp, sample = formd.plan_run(_platform_input({}))
    assert sample is False and inp["daysBack"] == 7


def test_explicit_sample_mode_ignores_filters_and_is_free():
    inp, sample = formd.plan_run(_platform_input({"sampleMode": True, "maxResults": 5000, "daysBack": 90,
                                                  "onlyNewSinceLastRun": True, "industries": ["Banking"]}))
    assert sample is True
    assert inp == formd.SAMPLE_INPUT and inp["maxResults"] == 5 and "onlyNewSinceLastRun" not in inp


def test_truly_empty_input_is_sample_for_local_runs():
    assert formd.plan_run({})[1] is True and formd.plan_run(None)[1] is True


def test_normal_paid_input_recognised():
    inp, sample = formd.plan_run(_platform_input({"sampleMode": False, "industries": ["Biotechnology"],
                                                  "minAmountSold": 1000000, "maxResults": 100}))
    assert sample is False and inp["industries"] == ["Biotechnology"] and inp["maxResults"] == 100


def test_sample_mode_defaults_off():
    assert SCHEMA["sampleMode"]["default"] is False and "prefill" not in SCHEMA["sampleMode"]
