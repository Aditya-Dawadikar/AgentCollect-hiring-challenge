# ABOUT.md

## Why this role

AI-native engineering is interesting precisely because "can the model do X"
is the easy part — the hard part is building the system *around* the model
so its output is something a human can actually trust: confidence scoring,
provenance, "I don't know" states, and graceful degradation. The Contact
Finder problem is that exact shape — combine fallible sources into a result
that's honest about what it doesn't know — and it's the same class of
problem I've been working on in AgentOS (giving AI agents a reliable
execution substrate). AgentCollect applying that discipline to real B2B
collections is what makes this role interesting to me.

## How you work with AI tools

I used Claude Code end-to-end for this challenge, directed rather than on
autopilot:

- **Stage A**: had it study the repo cold and write `PLAN.md` — including
  the scoring formula, conflict-handling rules, and clarifying questions —
  *before* reading `CLARIFICATIONS.md`, committed on its own so the
  timestamp reflects real upfront reasoning rather than hindsight.
- **Stage B**: broke the build into a tracked checklist (loaders, identity
  resolution, contact resolution, scoring, threshold gate, output, tests,
  docs) so progress and scope stayed visible rather than one big diff.
- **Verification over trust**: I don't trust a scoring heuristic just
  because the code runs — every one of the 30 mock rows was hand-traced
  against the scoring rules and matched before I accepted the
  implementation (`Processed 30 companies: 7 confident, 23
  needs_human_review`).
- **Surface divergence, don't paper over it**: when the real mock shapes
  diverged from `PLAN.md` (e.g. the `enrichment` provider never returns a
  `name`, so name-based cross-referencing became email-token matching), I
  had it document that adaptation explicitly in `DOCUMENTATION.md` /
  `slice/README.md` rather than silently adjusting the plan after the fact.

I trust the model for boilerplate (loaders, test scaffolding, CSV/JSON
plumbing, docs) but not to self-certify a scoring heuristic — that gets
checked against data, row by row.

## Your last project (structured — this is the pre-filter)

**Project**: [AgentOS](https://github.com/Aditya-Dawadikar/AgentOS) — a
Python/FastAPI/Docker platform letting AI agents submit jobs that run in
isolated containers, with lifecycle management, artifact collection, and
observability.

- **One ambiguity** you faced and how you resolved it: Whether to build a
  queue + worker pool from day one, or start synchronous. I shipped
  synchronous first to validate the core lifecycle (submit → execute →
  logs/artifacts → terminal state), then load-tested with Locust on a
  4-vCPU EC2 box. It held ~64 concurrent jobs reliably before P95/P99
  latency developed a long tail past 10s — that measurement, not a guess,
  is what told me a queue was actually needed.
- **One tradeoff** you made and why: Traded scalability for simplicity in
  v1 — no worker pool, no retries, no distributed scheduling — so I could
  verify container isolation, artifact collection, and failure handling
  actually worked before adding more moving parts on top of an unproven
  core.
- **One mistake** you made and what you changed: I underestimated how much
  harder *lifecycle* management is than just launching a container. I ended
  up writing a large Pytest suite covering creation, timeouts, termination,
  cleanup, and state transitions — it surfaced edge cases (process
  termination, cleanup ordering) I would not have caught manually.
- **One review comment** that made you change your mind: I was told I was
  solving scaling problems before validating the execution model — that
  complexity should be earned through evidence, not anticipated. That's why
  the queue/worker-pool redesign is the *next* milestone, backed by the
  Locust numbers, rather than where I started.

## Anything you'd improve about THIS challenge or our CLAUDE.md

- `challenge/mocks/README.md` frames the approach around cross-referencing
  by name, but the `enrichment` provider's fixtures never include a `name`
  field (only `email`/`phone`). A one-line note ("enrichment never returns
  a name — corroborate via email/phone instead") would save candidates a
  round of reverse-engineering the fixture shapes.
- `CLAUDE.md` is Laravel/PHP-specific (artisan commands, `tests/Unit` vs
  `tests/Feature`, `feat/TICKET-ID` branch naming), but the README says the
  Contact Finder is language-agnostic and to "skim it." It might be worth a
  one-line disclaimer that CLAUDE.md's *specific* commands/paths apply only
  to the legacy Laravel sandbox, so candidates don't second-guess whether
  `php artisan test --parallel` is somehow expected for the Contact Finder.
- Neither `PLAN.template.md` nor `ABOUT.template.md` says explicitly where
  `PLAN.md`/`ABOUT.md` should live (repo root vs. `challenge/`) — minor, but
  a one-line "place these at the repo root" would remove a small guess for
  candidates.


### How I start a fresh task?

Video Link: https://drive.google.com/file/d/1J9CO1ArfxQ4cxVw0GslRLCZfzptgiK8m/view?usp=sharing
