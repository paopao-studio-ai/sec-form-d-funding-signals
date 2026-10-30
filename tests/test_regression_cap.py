"""Regression: with changeTracking + maxResults, a second identical run must output 0 filings and report
0 new / 0 changed issuer rows. Runs the real Actor main() twice against local storage (EDGAR mocked)."""
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

RUNNER = textwrap.dedent('''
    import asyncio, sys
    from pathlib import Path
    sys.path.insert(0, %r)
    import src.main as m
    xml = (Path(%r) / "tests/fixtures/operating.xml").read_text()
    calls = {"n": 0}
    def fake_index(c, d, limiter, amend):
        calls["n"] += 1
        if calls["n"] > 1:
            return None
        return [{"form_type": "D", "company_name": f"Acme {i} Inc", "cik": str(1000 + i), "filed_date": d.isoformat(),
                 "accession_number": f"000{1000 + i}-26-000001", "path": f"edgar/data/{1000 + i}/x.txt"}
                for i in range(60)]
    class R:
        text = xml
    m.fetch_index = fake_index
    m._get = lambda c, url, limiter: R()
    asyncio.run(m.main())
''') % (str(ROOT), str(ROOT))


def _run(storage: Path, inp: dict) -> tuple[list[dict], dict]:
    kv = storage / "key_value_stores" / "default"
    kv.mkdir(parents=True, exist_ok=True)
    (kv / "INPUT.json").write_text(json.dumps(inp))
    ds = storage / "datasets" / "default"
    if ds.exists():
        for f in ds.glob("0*.json"):
            f.unlink()
    env = {**os.environ, "APIFY_LOCAL_STORAGE_DIR": str(storage), "CRAWLEE_STORAGE_DIR": str(storage),
           "CRAWLEE_PURGE_ON_START": "0"}
    subprocess.run([sys.executable, "-c", RUNNER], env=env, check=True, capture_output=True, timeout=120)
    rows = [json.loads(f.read_text()) for f in sorted(ds.glob("0*.json"))]
    summary = json.loads(next(kv.glob("RUN_SUMMARY*")).read_text())
    return rows, summary


def test_capped_change_tracking_second_run_is_empty(tmp_path):
    inp = {"daysBack": 7, "changeTracking": True, "maxResults": 5, "stateKey": "reg",
           "userAgent": "test paopaomusic@mail.grokbot.com"}
    rows1, s1 = _run(tmp_path, inp)
    assert len(rows1) == 5 and s1["skipped_by_max_results"] == 55
    rows2, s2 = _run(tmp_path, inp)
    assert rows2 == []
    assert (s2["pushed"], s2["new_issuer_rows"], s2["changed_issuer_rows"]) == (0, 0, 0)
    assert s2["skipped_seen"] == 60
