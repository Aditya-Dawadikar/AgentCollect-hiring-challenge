# TODO — Contact Finder (Stage B Build)

Tracking board for the Stage B implementation of the **Contact Finder** challenge
(`challenge/PROBLEM.md` + `challenge/CLARIFICATIONS.md`, plan committed in `PLAN.md`).

Goal: read `challenge/data/companies.csv` (30 companies), query the three mocked
providers in `challenge/mocks/enrichment_responses.json` (registry / listing /
enrichment), fuse the signals, score confidence with **two** independent
classifiers (rule-based + decision tree), output provenance-tracked contacts
with `needs_human_review` flags, and compare the two classifiers with
precision/recall/F1.

Everything lives under [`contact-finder/`](contact-finder/).

## Scope note

The repo also contains legacy tickets `TICKET-001`..`TICKET-004` (Laravel
sandbox bugs + the old "zero-budget creativity test" variant of the contact
finder). Per the repo `README.md` ("Do not do both"), this build targets the
**current** Contact Finder challenge (mocked providers, `PLAN.md` already
committed for Stage A). Legacy tickets are left untouched.

## Status legend
`[ ]` not started · `[~]` in progress · `[x]` done

## Build order (each ticket = one branch off `main`, merged back + pushed on completion)

- [x] [TICKET-005](tickets/TICKET-005-project-scaffolding-data-layer.md) — Project scaffolding & data layer
- [x] [TICKET-006](tickets/TICKET-006-name-email-phone-matchers.md) — Name / email / phone matching strategies
- [x] [TICKET-007](tickets/TICKET-007-signal-fusion-conflict-resolution.md) — Signal fusion & conflict resolution
- [x] [TICKET-008](tickets/TICKET-008-rule-based-classifier.md) — v1 rule-based confidence classifier
- [ ] [TICKET-009](tickets/TICKET-009-decision-tree-classifier.md) — v2 decision-tree classifier
- [ ] [TICKET-010](tickets/TICKET-010-evaluation-framework.md) — Evaluation framework (precision/recall/F1)
- [ ] [TICKET-011](tickets/TICKET-011-pipeline-output-formatter-readme.md) — Full pipeline, output formatter, README

## Decision records (ADRs)

Written as design decisions are made, in `contact-finder/docs/decisions/`.
Each ticket links the ADR(s) it produces. Index kept up to date here:

- [x] ADR-0001 — Dependency versions for Python 3.13 (deviating from pinned `requirements.txt` in the original build plan)
- [x] ADR-0002 — Name normalization & fuzzy-matching threshold
- [x] ADR-0003 — Source authority & conflict-resolution policy
- [x] ADR-0004 — Rule-based (v1) confidence weights
- [ ] ADR-0005 — Decision-tree (v2) features, training data, hyperparameters
- [ ] ADR-0006 — Evaluation methodology (what precision/recall/F1 are computed over, and why)
- [ ] ADR-0007 — Output schema extensions (provenance fields beyond the minimal spec)

## Working agreement

- Sequential build: each module's interface is consumed by the next
  (`signal_fusion` output -> `features` -> both classifiers -> `evaluation`),
  so tickets are executed in order, not in parallel.
- TDD per ticket: failing test first, then minimal implementation.
- One short-lived branch per ticket (`feat/TICKET-0XX-slug`), merged to `main`
  with `--no-ff`, then `git push origin main`. No feature branches pushed to
  `origin` — remote keeps a single `main` branch.
