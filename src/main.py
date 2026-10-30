"""Apify Actor: SEC Form D Funding Signals (newly funded US private companies, official EDGAR data).

Pure logic lives in src/formd.py; this file is only the Actor glue (input, state, charging, output).
Charged event (pay per event):
  filing   one Form D filing that passed your filters, pushed to the dataset
           (with changeTracking on, also an amendment to a tracked issuer: change_type "changed")
Index downloads, skipped filings, errors and the built-in sample are never charged.
"""
from __future__ import annotations

import asyncio
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from apify import Actor

from .formd import (SEC, RateLimiter, apply_tracking, fetch_index, make_client, matches, parse_form_d, plan_run,
                    prefilter_index, primary_doc_url, prior_edgar_filings, resolve_dates, score_filing,
                    update_issuers, _get, _lst)

STATE_STORE = "sec-form-d-funding-signals-state"


def _scan(inp: dict, seen: set[str] | None, log, tracked: set[str] | None = None, score: bool = False) -> dict:
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
            only_new = inp.get("onlyNewOfferings", True)
            got = fetch_index(c, d, limiter, (not only_new) or tracked is not None)
            if got is None:
                continue
            if only_new and tracked is not None:
                # Change tracking: amendments only matter for issuers we already track.
                got = [r for r in got if r["form_type"] != "D/A" or str(int(r["cik"])) in tracked]
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
                    amend_of_tracked = (tracked is not None and rec.get("is_amendment")
                                        and rec["cik"] in tracked)
                    if matches(rec, {**inp, "onlyNewOfferings": False} if amend_of_tracked else inp):
                        out.append(rec)
                if len(out) >= max_results:
                    break
        out.sort(key=lambda x: (x.get("filed_date") or "", x.get("total_amount_sold_usd") or 0), reverse=True)
        # Matches beyond maxResults stay "unseen" so the next monitor run still delivers them.
        dropped = {x["accession_number"] for x in out[max_results:]}
        out = out[:max_results]
        stats["matched"] = len(out)
        scanned = [a for a in processed if a not in dropped]
        if score:
            # One extra /Archives/ request per delivered filing: the issuer's EDGAR folder listing.
            targets = _lst(inp.get("scoreIndustries"))
            for rec in out:
                prior = None
                resp = _get(c, f"{SEC}/Archives/edgar/data/{rec['cik']}/index.json", limiter)
                if resp is not None:
                    try:
                        prior = prior_edgar_filings(resp.json(), rec["accession_number"], rec.get("filed_date"))
                    except ValueError:
                        prior = None
                stats["issuer_index_fetched"] = stats.get("issuer_index_fetched", 0) + 1
                rec.update(score_filing(rec, prior, targets))
    return {"records": out, "stats": stats, "scanned": scanned, "dates": [d.isoformat() for d in dates]}


async def main() -> None:
    async with Actor:
        raw: dict[str, Any] = await Actor.get_input() or {}
        inp, sample = plan_run(raw)
        if sample:
            Actor.log.info("Free sample mode - last 3 days, operating companies, 5 rows, filters ignored, not charged.")
        else:
            Actor.log.info(f"Paid run - each pushed filing is one 'filing' event (maxResults={inp.get('maxResults', 200)}).")
        track = bool(inp.get("changeTracking")) and not sample
        score = bool(inp.get("signalScoring"))
        monitor = bool(inp.get("onlyNewSinceLastRun")) and not sample and not track
        if track and inp.get("onlyNewSinceLastRun"):
            Actor.log.info("Change tracking is on - it replaces 'Only new since last run' for this run (that state is left untouched).")
        state_kv = await Actor.open_key_value_store(name=STATE_STORE) if (monitor or track) else None
        state_key = (inp.get("stateKey") or "default").strip() or "default"
        chg_key = "chg-" + (re.sub(r"[^A-Za-z0-9_.-]", "-", state_key)[:200] or "default")
        seen_list: list[str] = ((await state_kv.get_value(state_key)) or []) if (state_kv and monitor) else []
        chg_state: dict = ((await state_kv.get_value(chg_key)) or {}) if (state_kv and track) else {}
        issuers: dict = dict(chg_state.get("issuers") or {})
        if track:
            seen_list = list(chg_state.get("seen") or [])
        seen = set(seen_list) if (monitor or track) else None
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        res = await asyncio.to_thread(_scan, inp, seen, Actor.log, set(issuers) if track else None, score)
        if track:
            apply_tracking(res["records"], issuers, now_iso)
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
            if track:
                delivered = res["records"][:pushed]
                await state_kv.set_value(chg_key, {"v": 1, "seen": merged, "issuers": update_issuers(issuers, delivered, now_iso),
                                                    "updated_at": now_iso})
            else:
                await state_kv.set_value(state_key, merged)
        delivered = res["records"][:pushed]
        extra = {}
        if track:
            extra = {"change_tracking": True, "is_baseline_run": not chg_state,
                     "new_issuer_rows": sum(1 for r in delivered if r.get("change_type") == "new"),
                     "changed_issuer_rows": sum(1 for r in delivered if r.get("change_type") == "changed")}
        await Actor.set_value("RUN_SUMMARY", {**stats, **extra, "pushed": pushed, "sample": sample, "monitor": monitor,
                                               "charged_filing_events_requested": 0 if sample else pushed,
                                               "dates": res["dates"]})
        if stats["days_with_index"] == 0:
            await Actor.fail(status_message="No EDGAR daily index found for the requested dates (weekend/holiday or not yet published - indexes appear ~10pm ET).")
            return
        Actor.log.info(f"Done: pushed {pushed} filings.")
