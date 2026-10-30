"""Apify Actor: SEC Form D Funding Signals (newly funded US private companies, official EDGAR data).

Pure logic lives in src/formd.py; this file is only the Actor glue (input, state, charging, output).
Charged event (pay per event):
  filing   one Form D filing that passed your filters, pushed to the dataset
Index downloads, skipped filings, errors and the built-in sample are never charged.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from apify import Actor

from .formd import (RateLimiter, fetch_index, make_client, matches, parse_form_d, prefilter_index,
                    primary_doc_url, resolve_dates, _get)

STATE_STORE = "sec-form-d-funding-signals-state"
SAMPLE_INPUT = {"daysBack": 3, "maxResults": 5, "categories": ["operating_company"]}


def _scan(inp: dict, seen: set[str] | None, log) -> dict:
    """Sync work: indexes -> prefilter -> XML -> filter. Returns records + counters."""
    limiter = RateLimiter(float(inp.get("requestsPerSecond") or 5))
    dates = resolve_dates(inp)
    stats = {"days_requested": len(dates), "days_with_index": 0, "index_rows": 0, "after_prefilter": 0,
             "xml_fetched": 0, "xml_failed": 0, "matched": 0, "skipped_seen": 0}
    max_results = int(inp.get("maxResults") or 200)
    max_scan = int(inp.get("maxFilingsToScan") or 3000)
    with make_client(inp.get("userAgent")) as c:
        rows: list[dict] = []
        for d in sorted(dates, reverse=True):  # newest first
            got = fetch_index(c, d, limiter, not inp.get("onlyNewOfferings", True))
            if got is None:
                continue
            stats["days_with_index"] += 1
            rows.extend(got)
        stats["index_rows"] = len(rows)
        rows = prefilter_index(rows, inp)
        if seen is not None:
            before = len(rows)
            rows = [r for r in rows if r["accession_number"] not in seen]
            stats["skipped_seen"] = before - len(rows)
        stats["after_prefilter"] = len(rows)
        rows = rows[:max_scan]
        out: list[dict] = []
        processed: list[str] = []

        def one(r: dict):
            resp = _get(c, primary_doc_url(r), limiter)
            if resp is None:
                return r, None
            try:
                return r, parse_form_d(resp.text, r)
            except Exception as e:  # noqa: BLE001 - malformed XML should not kill the run
                log.warning(f"{r['accession_number']}: parse error {type(e).__name__}")
                return r, None

        # Small batches so we can stop fetching once maxResults is reached.
        with ThreadPoolExecutor(max_workers=4) as ex:
            for i in range(0, len(rows), 40):
                for r, rec in ex.map(one, rows[i:i + 40]):
                    if rec is None:
                        stats["xml_failed"] += 1
                        continue
                    stats["xml_fetched"] += 1
                    processed.append(r["accession_number"])
                    if matches(rec, inp):
                        out.append(rec)
                if len(out) >= max_results:
                    break
        out.sort(key=lambda x: (x.get("filed_date") or "", x.get("total_amount_sold_usd") or 0), reverse=True)
        # Matches beyond maxResults stay "unseen" so the next monitor run still delivers them.
        dropped = {x["accession_number"] for x in out[max_results:]}
        out = out[:max_results]
        stats["matched"] = len(out)
        scanned = [a for a in processed if a not in dropped]
    return {"records": out, "stats": stats, "scanned": scanned, "dates": [d.isoformat() for d in dates]}


async def main() -> None:
    async with Actor:
        raw: dict[str, Any] = await Actor.get_input() or {}
        sample = not any(v not in (None, "", [], {}) for v in raw.values())
        inp = {**SAMPLE_INPUT} if sample else {**raw}
        if sample:
            Actor.log.info("Empty input - running the built-in sample (last 3 days, 5 rows, not charged).")
        monitor = bool(inp.get("onlyNewSinceLastRun")) and not sample
        state_kv = await Actor.open_key_value_store(name=STATE_STORE) if monitor else None
        state_key = (inp.get("stateKey") or "default").strip() or "default"
        seen_list: list[str] = ((await state_kv.get_value(state_key)) or []) if state_kv else []
        seen = set(seen_list) if monitor else None

        res = await asyncio.to_thread(_scan, inp, seen, Actor.log)
        stats = res["stats"]
        Actor.log.info(f"Dates {res['dates'][-1] if res['dates'] else '-'}..{res['dates'][0] if res['dates'] else '-'}; {stats}")

        pushed = 0
        for rec in res["records"]:
            if sample:
                await Actor.push_data(rec)
            else:
                cr = await Actor.push_data(rec, charged_event_name="filing")
                if cr.event_charge_limit_reached:
                    Actor.log.info("Max charge per run reached - stopping output.")
                    pushed += 1
                    break
            pushed += 1

        if state_kv is not None:
            # Remember every filing we looked at (matched or not), capped to the newest 50k.
            unpushed = {r["accession_number"] for r in res["records"][pushed:]}  # charge limit hit
            merged = list(dict.fromkeys([a for a in res["scanned"] if a not in unpushed] + seen_list))[:50000]
            await state_kv.set_value(state_key, merged)
        await Actor.set_value("RUN_SUMMARY", {**stats, "pushed": pushed, "sample": sample, "monitor": monitor,
                                               "dates": res["dates"]})
        if stats["days_with_index"] == 0:
            await Actor.fail(status_message="No EDGAR daily index found for the requested dates (weekend/holiday or not yet published - indexes appear ~10pm ET).")
            return
        Actor.log.info(f"Done: pushed {pushed} filings.")
