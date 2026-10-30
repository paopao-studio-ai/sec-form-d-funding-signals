from datetime import date

from src.formd import apply_tracking, prior_edgar_filings, score_filing, update_issuers

TODAY = date(2026, 10, 30)


def _rec(**kw):
    base = {"cik": "123", "accession_number": "0001-26-000001", "company_name": "Acme AI Inc", "filed_date": "2026-10-29",
            "is_amendment": False, "total_amount_sold_usd": 5_000_000.0, "incorporated_within_5_years": True,
            "year_of_inc": 2025, "industry_group": "Other Technology", "days_first_sale_to_filing": 10,
            "first_sale_yet_to_occur": False, "percent_sold": 100.0, "investors_count": 12}
    base.update(kw)
    return base


def test_score_is_explainable_and_bounded():
    s = score_filing(_rec(), prior_filings=0, today=TODAY)
    assert s["signal_score"] == sum(s["score_components"].values())
    assert 0 <= s["signal_score"] <= 100 and len(s["score_reasons"]) == 6
    assert s["is_first_edgar_filing"] is True and s["signal_tier"] == "hot"
    assert s["score_components"]["amount"] == 20  # $5M on a $100k..$100M log scale
    assert any("first EDGAR filing" in r for r in s["score_reasons"])


def test_score_amendment_old_finance_is_low():
    s = score_filing(_rec(is_amendment=True, total_amount_sold_usd=0, incorporated_within_5_years=False, year_of_inc=1990,
                          industry_group="Banking and Financial Services", days_first_sale_to_filing=None,
                          percent_sold=None, investors_count=None), prior_filings=40, today=TODAY)
    assert s["signal_score"] == 0 and s["signal_tier"] == "cold"


def test_score_target_industries():
    hit = score_filing(_rec(industry_group="Biotechnology"), 0, ["biotechnology"], today=TODAY)
    miss = score_filing(_rec(industry_group="Computers"), 0, ["biotechnology"], today=TODAY)
    assert hit["score_components"]["industry"] == 15 and miss["score_components"]["industry"] == 0


def test_prior_edgar_filings_counts_older_folders_only():
    idx = {"directory": {"item": [
        {"name": "000000126000001", "type": "folder.gif", "last-modified": "2026-10-29 10:00:00"},
        {"name": "000999925000001", "type": "folder.gif", "last-modified": "2025-01-02 10:00:00"},
        {"name": "000999926000009", "type": "folder.gif", "last-modified": "2026-10-30 10:00:00"},
        {"name": "index.json", "type": "file", "last-modified": "2020-01-01 00:00:00"}]}}
    assert prior_edgar_filings(idx, "0000001-26-000001", "2026-10-29") == 1
    assert prior_edgar_filings({}, "x", "2026-10-29") is None


def test_tracking_new_then_changed_with_delta():
    issuers = {}
    first = [_rec(total_amount_sold_usd=1_000_000.0)]
    apply_tracking(first, issuers, "2026-10-29T00:00:00Z")
    assert first[0]["change_type"] == "new" and first[0]["previous_amount_sold_usd"] is None
    issuers = update_issuers(issuers, first, "2026-10-29T00:00:00Z")
    second = [_rec(accession_number="0001-26-000002", is_amendment=True, form_type="D/A", total_amount_sold_usd=3_000_000.0)]
    apply_tracking(second, issuers, "2026-10-30T00:00:00Z")
    r = second[0]
    assert r["change_type"] == "changed" and r["previous_amount_sold_usd"] == 1_000_000.0
    assert r["amount_sold_delta_usd"] == 2_000_000.0 and r["previous_accession_number"] == "0001-26-000001"
    issuers = update_issuers(issuers, second, "2026-10-30T00:00:00Z")
    assert issuers["123"]["c"] == 2 and issuers["123"]["fs"] == "2026-10-29T00:00:00Z"
