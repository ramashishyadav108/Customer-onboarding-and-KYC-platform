# Debugging Log - environment-first resolution

Each entry: symptom, environment check that found the cause, fix. Environment problems were diagnosed before any code or spec was changed.

## 1. Harness source not found by `/scaffold`
- **Symptom:** reads of `~/claude-harness-engine/...` returned "file does not exist".
- **Check:** `Test-Path ~\claude-harness-engine` was False while `Resolve-Path ~` was `C:\Users\ray09`; `Get-ChildItem capstone4` showed a directory literally named `~`.
- **Cause:** the clone happened in a shell that did not expand `~`, creating `capstone4\~\claude-harness-engine`.
- **Fix:** scaffold was pointed at the real path; `~/` added to `.gitignore` so the stray folder is not committed.

## 2. `uv` assumed by the design but not installed
- **Symptom:** design and `init.sh` mixed `uv` and `venv` commands.
- **Check:** `which uv` -> not found; `python --version` -> 3.12.3; `node --version` -> 18.18.0.
- **Fix:** standardised on `python -m venv backend/.venv` + pip + `requirements.lock` (design decision DD-15); manifest, `init.sh`, `CLAUDE.md` updated. Spec unchanged.

## 3. Multi-file shell heredoc failed to parse
- **Symptom:** one large bash command wrote nothing (`unexpected EOF while looking for matching`).
- **Check:** `ls` of the target directories confirmed nothing had been created, so no partial state to clean.
- **Fix:** files were written one by one with the file-write tool; hooks were then exercised with piped JSON to confirm exit codes.

## 4. Node version constraint
- **Observation:** Node is 18.18.0. Newer Vite majors require Node 20+; the frontend must pin a Vite version that supports Node 18 (or Node must be upgraded). Recorded before scaffolding the frontend.
