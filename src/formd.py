"""Pure logic: SEC EDGAR daily index -> Form D primary_doc.xml -> normalized funding signal rows.

Data source: the SEC's public EDGAR archive (https://www.sec.gov/Archives/edgar/), which the SEC
offers for automated download under its fair-access policy (declared User-Agent, <= 10 requests/s).
No login, no proxy, no scraping of HTML pages.

Privacy: Form D lists "related persons" (executives, directors, promoters) with names and addresses,
and the issuer's street address and phone number. This module never outputs any of those. It keeps
only company-level facts (company name, CIK, city/state, industry, amounts, dates) and a count of
related persons by role.
"""
from __future__ import annotations

import re
import threading
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable

import httpx

SEC = "https://www.sec.gov"
DEFAULT_UA = "PaoPao Studio sec-form-d-funding-signals paopaomusic@mail.grokbot.com"

REAL_ESTATE = {"REITS and Finance", "Residential", "Commercial", "Construction", "Other Real Estate"}
POOLED = "Pooled Investment Fund"
# Names that are almost always investment vehicles rather than operating companies.
_SPV_RX = re.compile(
    r"\bSPV\b|\ba series of\b|\bseries [a-z0-9-]+ of\b|\bfund\b|\bfeeder\b|\bco-?invest|\bmaster\b.*\bL\.?P\.?$"
    r"|\bcapital partners\b|\bventures? (?:fund|partners)\b|\bopportunit(?:y|ies) (?:fund|zone)\b"
    r"|\b(?:investors|investments|holdings) [ivx]+\b|\bQOF\b|\bQOZB?\b|\bsyndicate\b",
    re.I,
)
_IDX_RX = re.compile(r"^(D/A|D)\s+(.+?)\s{2,}(\d{1,10})\s+(\d{8})\s+(edgar/\S+\.txt)\s*$")


class RateLimiter:
    """Thread-safe minimum interval between requests (SEC asks for <= 10 req/s; we default to 5)."""

    def __init__(self, per_second: float = 5.0):
        self.interval = 1.0 / max(0.5, min(per_second, 9.0))
        self._lock = threading.Lock()
        self._next = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            t = max(now, self._next)
            self._next = t + self.interval
        if t > now:
            time.sleep(t - now)


def make_client(user_agent: str | None = None) -> httpx.Client:
    ua = (user_agent or "").strip() or DEFAULT_UA
    return httpx.Client(headers={"User-Agent": ua, "Accept-Encoding": "gzip, deflate"}, timeout=30, follow_redirects=True)


def _get(client: httpx.Client, url: str, limiter: RateLimiter | None, tries: int = 4) -> httpx.Response | None:
    for i in range(tries):
        if limiter:
            limiter.wait()
        try:
            r = client.get(url)
        except httpx.HTTPError:
            time.sleep(1.5 * (i + 1))
            continue
        if r.status_code == 404:
            return None
        if r.status_code in (403, 429, 500, 502, 503, 504):
            time.sleep(2.0 * (i + 1))
            continue
        r.raise_for_status()
        return r
    return None


# ---------- dates & index ----------

def date_range(start: date, end: date) -> list[date]:
    if end < start:
        start, end = end, start
    out, d = [], start
    while d <= end:
        if d.weekday() < 5:  # EDGAR only disseminates on business days
            out.append(d)
        d += timedelta(days=1)
    return out


def resolve_dates(inp: dict, today: date | None = None) -> list[date]:
    today = today or datetime.now(timezone.utc).date()
    s, e = inp.get("startDate"), inp.get("endDate")
    if s:
        start = date.fromisoformat(str(s)[:10])
        end = date.fromisoformat(str(e)[:10]) if e else today
        return date_range(start, min(end, today))
    n = int(inp.get("daysBack") or 7)
    n = max(1, min(n, 90))
    return date_range(today - timedelta(days=n), today)


def index_url(d: date) -> str:
    q = (d.month - 1) // 3 + 1
    return f"{SEC}/Archives/edgar/daily-index/{d.year}/QTR{q}/form.{d:%Y%m%d}.idx"


def parse_index(text: str, include_amendments: bool = False) -> list[dict]:
    rows = []
    for line in text.splitlines():
        m = _IDX_RX.match(line)
        if not m:
            continue
        form, name, cik, filed, path = m.groups()
        if form == "D/A" and not include_amendments:
            continue
        acc = path.rsplit("/", 1)[-1][:-4]
        rows.append({
            "form_type": form, "company_name": name.strip(), "cik": cik, "filed_date": f"{filed[:4]}-{filed[4:6]}-{filed[6:]}",
            "accession_number": acc, "path": path,
        })
    return rows


def primary_doc_url(row: dict) -> str:
    acc = row["accession_number"]
    return f"{SEC}/Archives/edgar/data/{int(row['cik'])}/{acc.replace('-', '')}/primary_doc.xml"


def filing_index_url(row: dict) -> str:
    acc = row["accession_number"]
    return f"{SEC}/Archives/edgar/data/{int(row['cik'])}/{acc.replace('-', '')}/{acc}-index.htm"


def fetch_index(client: httpx.Client, d: date, limiter: RateLimiter | None, include_amendments: bool) -> list[dict] | None:
    r = _get(client, index_url(d), limiter)
    if r is None:
        return None
    return parse_index(r.text, include_amendments)


# ---------- Form D XML ----------

def _t(el: ET.Element | None, path: str) -> str | None:
    if el is None:
        return None
    x = el.find(path)
    if x is None or x.text is None:
        return None
    v = x.text.strip()
    return v or None


def _num(v: str | None) -> float | None:
    if v is None:
        return None
    try:
        return float(v.replace(",", ""))
    except ValueError:
        return None  # e.g. "Indefinite"


def _bool(v: str | None) -> bool | None:
    if v is None:
        return None
    return v.strip().lower() == "true"


def stage_hint(amount_sold: float | None, is_operating: bool) -> str | None:
    """Rough, clearly-labelled guess from amount sold. Form D has no round name."""
    if not is_operating or amount_sold is None or amount_sold <= 0:
        return None
    if amount_sold < 1_000_000:
        return "angel/pre-seed (<$1M)"
    if amount_sold < 5_000_000:
        return "seed ($1-5M)"
    if amount_sold < 20_000_000:
        return "series A range ($5-20M)"
    if amount_sold < 75_000_000:
        return "series B/C range ($20-75M)"
    return "late/growth (>$75M)"


def classify(name: str, industry: str | None) -> str:
    if industry == POOLED:
        return "pooled_fund"
    if _SPV_RX.search(name or "") or industry == "Investing":
        return "spv_or_vehicle"
    if industry in REAL_ESTATE:
        return "real_estate"
    return "operating_company"


def parse_form_d(xml_text: str, row: dict) -> dict:
    root = ET.fromstring(xml_text)
    iss = root.find("primaryIssuer")
    off = root.find("offeringData")
    name = _t(iss, "entityName") or row.get("company_name")
    industry = _t(off, "industryGroup/industryGroupType")
    fund_type = _t(off, "industryGroup/investmentFundInfo/investmentFundType")
    year_inc = _t(iss, "yearOfInc/value")
    within5 = _bool(_t(iss, "yearOfInc/withinFiveYears"))
    over5 = _bool(_t(iss, "yearOfInc/overFiveYears"))
    first_sale = _t(off, "typeOfFiling/dateOfFirstSale/value")
    first_sale_yet = _bool(_t(off, "typeOfFiling/dateOfFirstSale/yetToOccur"))
    total_offering_raw = _t(off, "offeringSalesAmounts/totalOfferingAmount")
    sold = _num(_t(off, "offeringSalesAmounts/totalAmountSold"))
    remaining_raw = _t(off, "offeringSalesAmounts/totalRemaining")
    sec_types = []
    sto = off.find("typesOfSecuritiesOffered") if off is not None else None
    if sto is not None:
        for ch in sto:
            tag = ch.tag
            if tag.startswith("is") and tag.endswith("Type") and (ch.text or "").strip().lower() == "true":
                sec_types.append(re.sub(r"(?<!^)(?=[A-Z])", " ", tag[2:-4]).lower())
        other = _t(sto, "descriptionOfOtherType")
        if other:
            sec_types.append(f"other: {other}")
    exemptions = [x.text.strip() for x in (off.findall("federalExemptionsExclusions/item") if off is not None else []) if x.text]
    roles: dict[str, int] = {}
    people = root.findall("relatedPersonsList/relatedPersonInfo")
    for p in people:
        for rel in p.findall("relatedPersonRelationshipList/relationship"):
            if rel.text:
                k = rel.text.strip()
                roles[k] = roles.get(k, 0) + 1
    category = classify(name, industry)
    is_op = category == "operating_company"
    filed = row.get("filed_date")
    days_to_file = None
    if first_sale and filed:
        try:
            days_to_file = (date.fromisoformat(filed) - date.fromisoformat(first_sale[:10])).days
        except ValueError:
            pass
    total_offering = _num(total_offering_raw)
    pct_sold = round(100 * sold / total_offering, 1) if sold is not None and total_offering else None
    return {
        "type": "form_d_filing",
        "company_name": name,
        "cik": str(int(row["cik"])),
        "accession_number": row["accession_number"],
        "form_type": row.get("form_type"),
        "is_amendment": _bool(_t(off, "typeOfFiling/newOrAmendment/isAmendment")),
        "filed_date": filed,
        "date_of_first_sale": first_sale,
        "first_sale_yet_to_occur": first_sale_yet,
        "days_first_sale_to_filing": days_to_file,
        "category": category,
        "is_operating_company": is_op,
        "industry_group": industry,
        "investment_fund_type": fund_type,
        "entity_type": _t(iss, "entityType"),
        "jurisdiction_of_inc": _t(iss, "jurisdictionOfInc"),
        "year_of_inc": int(year_inc) if year_inc and year_inc.isdigit() else None,
        "incorporated_within_5_years": within5 if within5 is not None else (False if over5 else None),
        "issuer_city": _t(iss, "issuerAddress/city"),
        "issuer_state": _t(iss, "issuerAddress/stateOrCountry"),
        "issuer_state_name": _t(iss, "issuerAddress/stateOrCountryDescription"),
        "revenue_range": _t(off, "issuerSize/revenueRange"),
        "total_offering_amount_usd": total_offering,
        "offering_amount_indefinite": (total_offering_raw or "").lower() == "indefinite",
        "total_amount_sold_usd": sold,
        "total_remaining_usd": _num(remaining_raw),
        "percent_sold": pct_sold,
        "minimum_investment_usd": _num(_t(off, "minimumInvestmentAccepted")),
        "securities_offered": sec_types,
        "federal_exemptions": exemptions,
        "is_rule_506c_general_solicitation": "06c" in exemptions,
        "more_than_one_year": _bool(_t(off, "durationOfOffering/moreThanOneYear")),
        "investors_count": int(_num(_t(off, "investors/totalNumberAlreadyInvested")) or 0) if _t(off, "investors/totalNumberAlreadyInvested") else None,
        "has_non_accredited_investors": _bool(_t(off, "investors/hasNonAccreditedInvestors")),
        "sales_commissions_usd": _num(_t(off, "salesCommissionsFindersFees/salesCommissions/dollarAmount")),
        "finders_fees_usd": _num(_t(off, "salesCommissionsFindersFees/findersFees/dollarAmount")),
        "uses_placement_agent": bool(root.findall("offeringData/salesCompensationList/recipient")),
        "related_persons_count": len(people),
        "related_person_roles": roles,
        "stage_hint": stage_hint(sold, is_op),
        "filing_url": filing_index_url(row),
        "xml_url": primary_doc_url(row),
        "edgar_company_url": f"{SEC}/edgar/browse/?CIK={int(row['cik'])}",
    }


# ---------- filters ----------

def _lst(v: Any) -> list[str]:
    if not v:
        return []
    if isinstance(v, str):
        v = v.replace("\n", ",").split(",")
    return [str(x).strip() for x in v if str(x).strip()]


def _word_in(kw: str, name: str) -> bool:
    """Short keywords (<=2 chars, e.g. 'AI') must be a whole word: hits 'CVAT.ai Corp', not 'Retail'/'Aino'.
    Longer keywords match a word prefix: 'bio' -> 'Biotech'."""
    tail = r"(?![a-z0-9])" if len(kw) <= 2 else ""
    return re.search(r"(?<![a-z0-9])" + re.escape(kw) + tail, name) is not None


def prefilter_index(rows: Iterable[dict], inp: dict) -> list[dict]:
    """Cheap name-level filters before any XML is fetched."""
    kws = [k.lower() for k in _lst(inp.get("companyKeywords"))]
    excl = [k.lower() for k in _lst(inp.get("excludeCompanyKeywords"))]
    cats = set(_lst(inp.get("categories")) or ["operating_company"])
    out = []
    for r in rows:
        n = r["company_name"].lower()
        if kws and not any(_word_in(k, n) for k in kws):
            continue
        if excl and any(_word_in(k, n) for k in excl):
            continue
        # Skip obvious vehicles by name only when the user doesn't want them anyway.
        if "spv_or_vehicle" not in cats and "pooled_fund" not in cats and _SPV_RX.search(r["company_name"]):
            continue
        out.append(r)
    return out


def matches(rec: dict, inp: dict) -> bool:
    cats = set(_lst(inp.get("categories")) or ["operating_company"])
    if rec["category"] not in cats:
        return False
    inds = [x.lower() for x in _lst(inp.get("industries"))]
    if inds and (rec.get("industry_group") or "").lower() not in inds:
        return False
    states = [x.upper() for x in _lst(inp.get("states"))]
    if states and (rec.get("issuer_state") or "").upper() not in states:
        return False
    mn, mx = inp.get("minAmountSold"), inp.get("maxAmountSold")
    sold = rec.get("total_amount_sold_usd")
    if mn not in (None, "", 0) and (sold is None or sold < float(mn)):
        return False
    if mx not in (None, "", 0) and (sold is None or sold > float(mx)):
        return False
    if inp.get("onlyIncorporatedWithin5Years") and rec.get("incorporated_within_5_years") is not True:
        return False
    if inp.get("onlyNewOfferings", True) and rec.get("is_amendment"):
        return False
    return True
