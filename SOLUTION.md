# SOLUTION.md

## Query Optimization

### What was changed
- Added WAL journal mode to SQLite — allows concurrent reads during write operations
- Added indexes on `gender`, `country_id`, `age_group`, `age` — the four most
  frequently filtered columns
- Introduced an in-process TTLCache — repeated queries never hit the database

### Design decisions and trade-offs
- Chose in-process TTLCache over Redis — no extra infrastructure, no network calls,
  good enough for single-node deployment. Trade-off: cache is lost on restart and
  not shared across multiple instances
- WAL mode chosen over default journal mode — directly addresses contention between
  CSV ingestion writes and concurrent read queries

## Query Normalization

### What was changed
- Parse filters into a canonical dict
- Serialize with `sort_keys=True` to guarantee consistent key ordering
- MD5 hash the result into a fixed-length cache key

### Why
Two queries that express the same intent but different wording produce identical
filter dicts. Without normalization they produce different cache keys and cause
redundant DB hits.

### Trade-off
Slightly more computation per request. Negligible compared to the DB round trip
it eliminates.

## Before/After Comparison

| Scenario | Requests | DB Queries Hit | Cache Hits |
|---|---|---|---|
| 10 identical filtered queries | 10 | 1 | 9 |
| 10 identical search queries | 10 | 1 | 9 |
| 10 varied unique queries | 10 | 10 | 0 (expected) |
| **Total** | **30** | **12** | **18** |

18 out of 30 requests served entirely from cache — 60% reduction in database
load under repeated query patterns. Under real usage where analysts run the
same queries repeatedly, this number trends higher.

## CSV Ingestion

### Approach
- File streamed via `TextIOWrapper` — never loaded fully into memory
- Processed in chunks of 1000 rows — minimal DB round trips
- All existing profile names loaded into a Python set at upload start —
  O(1) duplicate checks throughout ingestion without per-row DB queries
- INSERT OR IGNORE used as concurrency safety net for simultaneous uploads
- `run_in_threadpool` used to offload sync processing off the event loop —
  uploads do not block concurrent query requests

### Failure handling
- Malformed rows — caught by outer try/except, counted and skipped
- Missing fields — checked before any processing, skipped with reason recorded
- Invalid values — age must be non-negative integer, gender must be male/female
- Duplicate names — checked against in-memory set before insert
- A single bad row never fails the upload — processing continues to EOF
- Partial failures do not rollback — already inserted rows remain

### Trade-off
- Loading all names into memory at upload start costs RAM proportional to
  table size. At 10 million rows (~500MB) this becomes a concern worth
  revisiting with a bloom filter or chunked name lookup strategy.