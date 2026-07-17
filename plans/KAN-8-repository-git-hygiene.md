# KAN-8 Repository and Git Hygiene Plan

## 1. Objective
Remove tracked local environment, IDE, cache, packaging, and conclusively generated runtime artifacts through a normal Git commit; repair the broken self-referential gitlink; and add reproducible hygiene verification without rewriting history or changing market datasets.

## 2. Jira and Specification Trace
Jira key: `KAN-8` - Repository and Git hygiene.

Specifications and audits read before implementation:
- `AGENTS.md`
- `PLANS.md`
- `PROJECT_SPEC.md`
- `DATA_CONTRACT.md`
- `DOMAIN_RULES.md`
- `ACCEPTANCE_CRITERIA.md`
- `docs/audits/data-and-git-hygiene.md`
- `docs/audits/migration-backlog.md`

The historical KAN-1 backlog labels this cleanup as KAN-3. This implementation follows the approved current Jira key, KAN-8, without rewriting the historical audit.

Acceptance trace:
- Tracked environment, IDE, cache, build, distribution, and egg-info paths are absent after the commit.
- Ignore rules prevent those categories from being re-added.
- The broken `P` gitlink is removed only because Git evidence proves it is an orphaned self-reference with no unique content outside repository history.
- Dataset paths and SHA-256 hashes remain unchanged.
- Python 3.11 editable installation, pytest, pip consistency, and GitHub Actions pass.

## 3. Current-State Evidence
Baseline ref: `origin/main` / `origin/KAN-8-repository-git-hygiene` at `fd7e8fb`.

Tracked baseline, computed from `git ls-tree -r -l HEAD`:
- Paths: 6,728.
- Aggregate tracked blob bytes: 240,406,069.
- `venv/`: 6,546 paths and 138,772,170 bytes.
- `.vs/`: 11 paths and 10,106,216 bytes.
- No tracked `.venv/`, `__pycache__/`, `.pytest_cache/`, `build/`, `dist/`, or `*.egg-info/` paths at baseline.

Dataset baseline, computed from sorted tracked paths and full file SHA-256 values:
- Paths: 56.
- Bytes: 90,960,790.
- Aggregate manifest SHA-256: `781d03bc4763b8654d9eaa5843d40a77ff1123a6d17db0b24179b2bb89c68543`.

Gitlink evidence:
- Index entry: mode `160000`, object `2fdb0efcd422df03e595ea543a722c39322170e3`, path `P`.
- `.gitmodules` is absent from both the worktree and tracked index.
- `git submodule status --recursive` fails with no submodule mapping for `P`.
- The object exists and is a commit named from `origin/feature/displacement-engine-pro`.
- `git merge-base --is-ancestor 2fdb0ef... HEAD` succeeds, proving the target is an older commit in this same repository history.
- Commit `c4c86b0` on the existing `smcp-v3-corrected-patch` branch removes the identical object/path with message `Remove accidental nested repository P`.
- Therefore the gitlink stores no unique subproject content: its referenced tree remains reachable in this repository history after removing the pointer.

## 4. Assumptions and Domain Questions
Implementation assumptions:
- `git rm --cached` is the appropriate non-destructive index operation for local artifacts; no history rewrite is needed.
- A tracked path with no current matches still requires an ignore rule to prevent recurrence.
- Root artifacts are removed only when source evidence identifies a regeneration path or proves they are local-only/stale.
- `.vscode/` is not in the approved removal list and may contain shared project configuration, so it remains tracked.

Market hypotheses: none. This cleanup does not change analytical logic, labels, timestamps, data gates, or execution behavior.

Human blockers: none for the `P` gitlink because its object identity, ancestry, and prior cleanup commit resolve the ambiguity. Artifact ambiguities are handled conservatively by retaining the files.

## 5. Proposed Architecture
- `.gitignore` is the policy boundary for local environment, IDE, cache, packaging, and selected root runtime outputs.
- `scripts/verify_git_hygiene.py` inspects the Git index, reports tracked path/blob totals and dataset integrity, rejects forbidden categories, and runs the submodule status check without modifying files.
- GitHub Actions invokes the same verification script before pytest so hygiene regressions fail CI.
- Dataset integrity is demonstrated by before/after path count, byte count, and aggregate full-hash manifest digest.

## 6. File-Level Change Map
Create:
- `plans/KAN-8-repository-git-hygiene.md`
- `scripts/verify_git_hygiene.py`

Modify:
- `.gitignore`
- `.github/workflows/pylint.yml`

Remove from the tracked index in a normal commit:
- `venv/`
- `.vs/`
- broken gitlink `P`
- `live_prices.json`
- `project_tree.txt`

Leave tracked and unchanged due ambiguity or source value:
- `dashboard.html`: static product/live viewer; no exact tracked generator reproduces it.
- `dashboard_enhanced.html`: product/report UI; `dashboard_generator.py` defaults to a different `dashboard_live.html` output.
- `Untitled-2.txt`: zero-byte and suspicious, but provenance is ambiguous and it is outside the approved artifact list.
- `08_order_blocks.pub`: unknown publication/source artifact with no conclusive regeneration evidence.
- `.vscode/`: potentially shared editor configuration and outside the approved removal list.

Leave entirely untouched:
- `raw_data/`
- `data_clean/`
- `data_features/`

## 7. Implementation Steps
1. Record baseline counts, hashes, artifact classifications, and gitlink evidence in this plan as the first tracked edit.
2. Strengthen `.gitignore` for every approved local/development category and the two proven root runtime artifacts.
3. Add a read-only Python 3.11 hygiene verifier and run it in GitHub Actions.
4. Remove approved paths from the index with `git rm --cached`, including the proven orphaned gitlink.
5. Recompute tracked totals and dataset integrity evidence.
6. Create a fresh Python 3.11 virtual environment, install `.[test]`, run the verifier and full pytest suite, and run `pip check`.
7. Commit and push the existing branch, open one draft PR with the required title, wait for Actions, and stop for human review.

## 8. Verification
Required checks:
- `git diff --check`
- `python scripts/verify_git_hygiene.py`
- `git ls-files` forbidden-category scan
- `git submodule status --recursive`
- before/after dataset path, byte, and aggregate SHA-256 comparison
- `python --version`
- `python -m venv .venv`
- `.venv` Python: `python -m pip install -e ".[test]"`
- `.venv` Python: `python -m pytest -q`
- `.venv` Python: `python -m pip check`
- GitHub Actions on the final PR head

No destructive Git command, force push, broker access, analytical run, or dataset rewrite is part of verification.

## 9. Data and Migration Impact
There is no dataset migration. The 56 tracked files under `raw_data/`, `data_clean/`, and `data_features/` remain at the same paths with identical bytes and SHA-256 values.

The cleanup affects only the current tree/index. Existing history still contains removed environment and IDE blobs; repository pack size will not materially shrink until an explicitly approved history rewrite, which is forbidden in this task.

Rollback is a normal revert of the KAN-8 commit. Local ignored copies left by `git rm --cached` are not part of repository rollback.

## 10. Risks and Limitations
- Clone size retains historical bloat because no `git filter-repo`, BFG, force push, or history rewrite is allowed.
- Dashboard provenance remains ambiguous, so both HTML files stay tracked.
- `Untitled-2.txt`, `08_order_blocks.pub`, and `.vscode/` remain unresolved classifications and are intentionally retained.
- Look-ahead, repainting, survivorship, timezone/DST, execution costs, and proxy-evidence limitations are unchanged because analytical and data surfaces are untouched.
- The hygiene verifier checks current tracked state and dataset content; it does not validate market semantics or provenance.

## 11. Progress Log
- 2026-07-17: Confirmed GitHub CLI 2.96.0 is authenticated as `0022249141`.
- 2026-07-17: Confirmed the existing KAN-8 branch equals `origin/main` and has no existing PR.
- 2026-07-17: Created an isolated sibling worktree at `P-KAN-8-repository-git-hygiene`.
- 2026-07-17: Read all required governance and audit files.
- 2026-07-17: Recorded baseline index, dataset, gitlink, and root-artifact evidence.
- 2026-07-17: Created this plan as the first tracked edit.
- 2026-07-17: Strengthened ignore policy and added `scripts/verify_git_hygiene.py` plus CI enforcement.
- 2026-07-17: Removed 6,560 approved paths from the index with `git rm --cached`; local ignored copies remain in the isolated worktree.
- 2026-07-17: Removed the proven self-referential `P` gitlink; `git submodule status --recursive` now succeeds.
- 2026-07-17: Created a fresh Python 3.11 environment, installed `.[test]`, and completed local verification.

## 12. Completion Evidence
Tracked-state comparison:

| Metric | Before | After | Change |
| --- | ---: | ---: | ---: |
| Tracked paths | 6,728 | 170 | -6,558 net |
| Tracked blob bytes | 240,406,069 | 91,528,440 | -148,877,629 |

Exact index removals:

| Category | Paths | Blob bytes |
| --- | ---: | ---: |
| `venv/` | 6,546 | 138,772,170 |
| `.vs/` | 11 | 10,106,216 |
| Broken gitlink `P` | 1 | 0 (gitlink, not blob) |
| `live_prices.json` | 1 | 147 |
| `project_tree.txt` | 1 | 17,470 |
| Total removed | 6,560 | 148,896,003 |

No tracked `.venv/`, `__pycache__/`, `.pytest_cache/`, `build/`, `dist/`, or `*.egg-info/` paths existed at baseline; their strengthened ignore rules and verifier probes prevent recurrence. Two new tracked files were added: this plan and the hygiene verifier.

Dataset integrity comparison:

| Metric | Before | After |
| --- | ---: | ---: |
| Paths under protected dataset directories | 56 | 56 |
| Bytes | 90,960,790 | 90,960,790 |
| Aggregate full-hash manifest SHA-256 | `781d03bc4763b8654d9eaa5843d40a77ff1123a6d17db0b24179b2bb89c68543` | `781d03bc4763b8654d9eaa5843d40a77ff1123a6d17db0b24179b2bb89c68543` |
| Staged dataset diff | none | none |

Command and result ledger:

| Command | Result |
| --- | --- |
| `git ls-tree -r -l HEAD` tracked-state calculation | Passed: 6,728 paths and 240,406,069 blob bytes before cleanup. |
| `git ls-files` category scan | Passed: identified 6,546 `venv/` and 11 `.vs/` paths; all other requested local categories had zero tracked paths. |
| `git ls-files --stage -- P` | Recorded mode `160000` and object `2fdb0efcd422df03e595ea543a722c39322170e3`. |
| `.gitmodules` worktree/index checks | Confirmed absent. |
| `git cat-file -t/-p 2fdb0ef...` | Passed: object exists as a commit in this repository. |
| `git merge-base --is-ancestor 2fdb0ef... HEAD` | Passed: target is an ancestor of the current repository, not unique subproject history. |
| `git show c4c86b0 -- P` | Confirmed an existing branch removes the identical pointer as an accidental nested repository. |
| Initial `git submodule status --recursive` | Failed as expected: no `.gitmodules` mapping for `P`; this was the known baseline defect. |
| `git rm -r --cached ...` and `git rm --cached P live_prices.json project_tree.txt` | Passed: 6,560 index deletions; local copies preserved. |
| `python --version` | Passed: Python 3.11.9. |
| `python -m venv .venv` | Passed. |
| `.\.venv\Scripts\python.exe -m pip install --upgrade pip` | Passed: pip 26.1.2. |
| `.\.venv\Scripts\python.exe -m pip install -e ".[test]"` | Passed. |
| `.\.venv\Scripts\python.exe scripts\verify_git_hygiene.py` | Passed: zero forbidden tracked paths, zero ignore-probe failures, zero gitlinks, submodule status 0, and unchanged dataset fingerprint. |
| `.\.venv\Scripts\python.exe -m pytest -q` | Passed: 30 tests in 1.38 seconds. |
| `.\.venv\Scripts\python.exe -m pip check` | Passed: no broken requirements. |
| `git diff --check` and `git diff --cached --check` | Passed independently with exit code 0. |
| `git submodule status --recursive` after cleanup | Passed with exit code 0. |
| `git diff --cached --quiet -- raw_data data_clean data_features` | Passed with exit code 0; no protected dataset change. |
| Combined parallel diagnostic wrapper | Returned exit 1 without failing-check output; every required command was rerun independently and passed. |

Artifact classification outcome:
- Removed: `live_prices.json` has an explicit runtime writer in `live_data_server.py`; `project_tree.txt` is a stale local inventory containing developer-specific absolute paths and `.git` internals.
- Retained: `dashboard.html` and `dashboard_enhanced.html` have no exact documented regeneration path.
- Retained as unresolved ambiguity: `Untitled-2.txt`, `08_order_blocks.pub`, and `.vscode/`.

Limitations:
- Historical Git packs still contain removed blobs; no history rewrite was performed.
- Artifact ambiguities listed above require separate human decisions before any future untracking.
- No market dataset, analytical engine, schema, or result was modified.
- Commit, draft PR, and GitHub Actions evidence remain pending publication.
