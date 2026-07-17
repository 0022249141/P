# Canonical Data Quality Gates

`pipelines.canonical` is the governed, in-memory market-data boundary introduced by
KAN-10. It does not open repository files, write outputs, access a network or broker,
or infer market semantics from names and paths.

## Contract

Canonical columns are ordered exactly as:

```text
timestamp,open,high,low,close,volume
```

Callers supply a `CanonicalizationPolicy` with explicit timezone evidence,
period-start or period-end semantics, duplicate behavior, gap behavior, and optional
versioned calendar evidence. Unknown timezone or period semantics blocks canonical
UTC output. Validation-only and duplicate rejection are the defaults. A non-reject
duplicate policy requires repair mode and emits source-row lineage and repair records.

Price units and volume meaning remain `UNKNOWN` unless declared. Strictly positive
prices are enforced only when the supplied price-unit declaration requests that rule.

## Gates

| Gate | KAN-10 behavior |
| --- | --- |
| G0 | Matches supplied dataset identity to one in-memory KAN-9 manifest record. |
| G1 | Validates canonical schema and explicit parser diagnostics. |
| G2 | Validates timezone, period semantics, ordering, DST, and duplicates. |
| G3 | Validates finite numeric values, volume, and OHLC geometry. |
| G4 | Evaluates intervals, gaps, coverage, and supplied versioned sessions. |
| G5 | Reconciles deterministic resampling against supplied HTF bars. |
| G6-G9 | Defined but `NOT_EVALUATED`; no evaluator is implemented in KAN-10. |

Every requested eligibility gate must appear exactly once with status `PASS` before
`execute_if_eligible` invokes its callback. `FAIL`, `BLOCKED`, `NOT_EVALUATED`, missing,
and duplicate results all block execution.

## Resampling

`resample_bars` supports M1 to M5, M15, M30, H1, H4, and D1. Its policy persists the
source and target timeframes, source period semantics, timestamp label, closed edge,
origin, offset, UTC requirement, calendar version and behavior, incomplete-bin action,
and volume aggregation. KAN-10 implements continuous-calendar binning. A versioned
session policy is rejected until an approved calendar binning implementation is
supplied; it is never approximated with hard-coded hours.

## Limitations

- The API trusts supplied semantic evidence; it does not discover broker timezones,
  holidays, sessions, price units, or volume meaning.
- G0 consumes manifest data supplied by the caller and does not reopen protected CSVs.
- G5 tolerances are explicit decimal strings; tolerance matches are reported separately
  from exact matches.
- No analytical, backtest, reporting, or live engine is wired to these gates yet.
- Committed research datasets remain immutable and are not used by ordinary tests.
