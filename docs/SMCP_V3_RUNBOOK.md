# SMCP V3 Operational Runbook

## Stable Branch

smcp-v3-architecture

## Current Production Baseline

Tests: 17 passed
Audit: 27/27 OK
Pipeline: 18/18 OK
Validation: 18/18 OK
Manifest: final_status = ok
Signals: 151
Trades: 151
Long: 90
Short: 61

## Activate Environment

(Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned) ; (& .\venv\Scripts\Activate.ps1)

## Run Tests

pytest tests -v

Expected:

17 passed

## Run Data Quality Audit

python .\scripts\run_data_quality_audit.py --data-dir data_clean --output output_fixed/data_quality_audit.csv

Expected:

Total files: 27
OK: 27
Failed: 0

## Run Pipeline

python .\scripts\run_smcp_v3_pipeline.py --data-dir data_clean --output-dir output_fixed --timeframes 5 15 30 60 240 1D --tail-rows 5000

Expected:

18 pipeline outputs
0 failed

## Validate Pipeline Outputs

python .\scripts\validate_pipeline_outputs.py --summary output_fixed/pipeline_v3_summary.csv --output output_fixed/pipeline_v3_validation_report.csv

Expected:

Checked outputs: 18
Failed: 0

## Generate Workflow Manifest

python .\scripts\write_workflow_manifest.py --audit output_fixed/data_quality_audit.csv --summary output_fixed/pipeline_v3_summary.csv --validation output_fixed/pipeline_v3_validation_report.csv --output output_fixed/workflow_run_manifest.json

Expected:

Final status: ok
Audit: 27/27 OK
Pipeline: 18/18 OK
Validation: 18/18 OK

## Preferred One-Command Workflow

python .\scripts\run_smcp_v3_workflow.py --data-dir data_clean --output-dir output_fixed --timeframes 5 15 30 60 240 1D --tail-rows 5000

Expected final output:

SMCP V3 WORKFLOW COMPLETED SUCCESSFULLY

## Main Outputs

output_fixed/data_quality_audit.csv
output_fixed/pipeline_v3_summary.csv
output_fixed/pipeline_v3_validation_report.csv
output_fixed/workflow_run_manifest.json
output_fixed/pipeline_v3/

## Git Commands

git status --short
git log --oneline -10

## Output Policy

Do not commit output_fixed/.
It is runtime-generated.

Commit only source code, scripts, tests, docs, and configuration.

## Next Hardening Targets

1. Add timestamped run-history archive.
2. Add output schema checks for execution plans.
3. Add configurable market/session calendars.
4. Add performance guardrails for full 50k-row runs.
5. Connect validated outputs to backend/dashboard.
