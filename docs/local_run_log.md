# Local run logs (2026-10-30 02:09 UTC)

## paid
```
[apify] INFO  Initializing Actor ({"apify_sdk_version": "4.1.0", "apify_client_version": "3.4.0", "crawlee_version": "1.11.0", "python_version": "3.13.5", "os": "linux", "is_running_in_ipython": false})
[apify] INFO  Dates 2026-10-30..2026-10-27; {'days_requested': 4, 'days_with_index': 3, 'index_rows': 452, 'after_prefilter': 245, 'xml_fetched': 120, 'xml_failed': 0, 'matched': 10, 'skipped_seen': 0}
[apify._charging] WARN  Ignored attempt to charge for an event - the Actor does not use the pay-per-event pricing
[apify] INFO  Done: pushed 10 filings.
[apify] INFO  Exiting Actor ({"exit_code": 0})
```

## mon2
```
[apify] INFO  Initializing Actor ({"apify_sdk_version": "4.1.0", "apify_client_version": "3.4.0", "crawlee_version": "1.11.0", "python_version": "3.13.5", "os": "linux", "is_running_in_ipython": false})
[apify] INFO  Dates 2026-10-30..2026-10-27; {'days_requested': 4, 'days_with_index': 3, 'index_rows': 452, 'after_prefilter': 125, 'xml_fetched': 120, 'xml_failed': 0, 'matched': 10, 'skipped_seen': 120}
[apify._charging] WARN  Ignored attempt to charge for an event - the Actor does not use the pay-per-event pricing
[apify] INFO  Done: pushed 10 filings.
[apify] INFO  Exiting Actor ({"exit_code": 0})
```

## sample
```
[apify] INFO  Initializing Actor ({"apify_sdk_version": "4.1.0", "apify_client_version": "3.4.0", "crawlee_version": "1.11.0", "python_version": "3.13.5", "os": "linux", "is_running_in_ipython": false})
[apify] INFO  Empty input - running the built-in sample (last 3 days, 5 rows, not charged).
[apify] INFO  Dates 2026-10-30..2026-10-27; {'days_requested': 4, 'days_with_index': 3, 'index_rows': 452, 'after_prefilter': 245, 'xml_fetched': 40, 'xml_failed': 0, 'matched': 5, 'skipped_seen': 0}
[apify] INFO  Done: pushed 5 filings.
[apify] INFO  Exiting Actor ({"exit_code": 0})
```

## v1.1 platform-input simulation (2026-10-30 02:26 UTC, ACTOR_TEST_PAY_PER_EVENT=true)

### prefill input
```json
{"sampleMode": false, "daysBack": 7, "categories": ["operating_company"], "onlyIncorporatedWithin5Years": false, "onlyNewOfferings": true, "onlyNewSinceLastRun": false, "stateKey": "default", "maxResults": 20, "maxFilingsToScan": 3000, "requestsPerSecond": 5, "industries": ["Other Technology", "Computers", "Biotechnology", "Other Health Care"], "states": [], "minAmountSold": 500000}
```
```
[apify] INFO  Initializing Actor ({"apify_sdk_version": "4.1.0", "apify_client_version": "3.4.0", "crawlee_version": "1.11.0", "python_version": "3.13.5", "os": "linux", "is_running_in_ipython": false})
[apify] INFO  Paid run - each pushed filing is one 'filing' event (maxResults=20).
[apify] INFO  Dates 2026-10-30..2026-10-23; {'days_requested': 6, 'days_with_index': 5, 'index_rows': 748, 'after_prefilter': 435, 'xml_fetched': 240, 'xml_failed': 0, 'matched': 20, 'skipped_seen': 0}
[apify] INFO  Done: pushed 20 filings.
[apify] INFO  Exiting Actor ({"exit_code": 0})
```
charging-log events: {'filing': 20, 'apify-default-dataset-item': 20} (apify-default-dataset-item is a synthetic SDK event; not configured in this Actor pricing so not billed on the platform)

### sample input
```json
{"sampleMode": true, "daysBack": 7, "categories": ["operating_company"], "onlyIncorporatedWithin5Years": false, "onlyNewOfferings": true, "onlyNewSinceLastRun": false, "stateKey": "default", "maxResults": 20, "maxFilingsToScan": 3000, "requestsPerSecond": 5, "industries": ["Other Technology", "Computers", "Biotechnology", "Other Health Care"], "states": [], "minAmountSold": 500000}
```
```
[apify] INFO  Initializing Actor ({"apify_sdk_version": "4.1.0", "apify_client_version": "3.4.0", "crawlee_version": "1.11.0", "python_version": "3.13.5", "os": "linux", "is_running_in_ipython": false})
[apify] INFO  Free sample mode - last 3 days, operating companies, 5 rows, filters ignored, not charged.
[apify] INFO  Dates 2026-10-30..2026-10-27; {'days_requested': 4, 'days_with_index': 3, 'index_rows': 452, 'after_prefilter': 245, 'xml_fetched': 40, 'xml_failed': 0, 'matched': 5, 'skipped_seen': 0}
[apify] INFO  Done: pushed 5 filings.
[apify] INFO  Exiting Actor ({"exit_code": 0})
```
charging-log events: {'apify-default-dataset-item': 5} (apify-default-dataset-item is a synthetic SDK event; not configured in this Actor pricing so not billed on the platform)
