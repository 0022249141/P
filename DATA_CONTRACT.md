# Market Data Contract

## Canonical bar schema
Required fields:

```text
timestamp,open,high,low,close,volume
```

Optional metadata fields may include:

```text
market,symbol,timeframe,source,broker,timezone,session,ingested_at,source_hash
```

## Type and semantic requirements
- `timestamp`: timezone-aware instant; normalized to UTC internally.
- `open,high,low,close`: finite decimal-compatible numeric values in the documented market unit.
- `volume`: non-negative; source meaning must be declared (`tick`, `real`, `proxy`, or `unknown`).
- Bars use explicit period-start or period-end semantics; never infer silently.
- Price units must be declared per dataset. Tehran Abshodeh reference output uses million tomans per mesghal when requested, while stored raw units remain unchanged.

## Raw-data rules
- Raw input is immutable.
- Record file hash, byte size, source path, ingestion time, parser version, and declared/inferred timezone.
- Never overwrite raw data during normalization.
- Headerless files require an explicit positional schema and a recorded parser decision.
- Missing timezone or calendar semantics must be labeled `INFERRED` until verified.

## Validation gates G0–G9
- G0: file inventory and provenance
- G1: schema and parsing integrity
- G2: temporal ordering, timezone, duplicates, and timestamp semantics
- G3: OHLC integrity and numeric validity
- G4: calendar, gaps, session anchors, and coverage
- G5: multi-timeframe reconciliation
- G6: deterministic feature reproduction
- G7: analytical eligibility
- G8: statistical eligibility
- G9: execution-backtest eligibility

A downstream engine may only consume a dataset when its required gates pass.

## OHLC integrity
For every bar:
- `high >= max(open, close, low)`
- `low <= min(open, close, high)`
- prices are finite and positive where the market contract requires positivity
- duplicate timestamps are rejected or resolved by an explicit policy

## Resampling
- Resample only from a validated lower timeframe.
- Aggregation is deterministic: first open, maximum high, minimum low, last close, declared volume aggregation.
- Session/calendar boundaries are explicit and versioned.
- M1-to-M5/M15/M30/H1/H4/D1 reconciliation requires tests.

## Run manifest
Each analytical run must record at least:
- code revision and git dirty status
- git diff hash when dirty
- CLI arguments and entrypoint
- configuration snapshot path/hash
- source file hashes and byte sizes
- locale and timezone
- calendar version and bar-builder version
- Python, pandas, numpy, and floating-point backend versions/settings
- random seeds

## Data layout target

```text
data/
  raw/<market>/
  staged/<market>/
  curated/<market>/
  manifests/
  artifacts/
```

Large or sensitive datasets should remain local or use approved large-file storage; committing them to normal Git history requires explicit approval.
