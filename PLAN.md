# PLAN.md

## Architecture

A small pipeline (implemented as a Python script for Stage B), one pure-function stage per step:

1. **Loader** — reads `companies.csv` into normalized records (`company_name`, `mailing_address`, plus a `state` parsed out of the address for later jurisdiction-aware lookups).
2. **Source adapters** — one adapter per provider (registry, listing, enrichment, ...future sources), each implementing the same interface: `lookup(company_name) -> RawResult | None`. Adapters absorb each provider's quirks (missing keys, null fields, different schemas) behind a uniform contract, so a mock can later be swapped for a real API by changing one file.
3. **Aggregator** — calls every adapter for a company, collects whatever comes back, and normalizes person names (case, whitespace, honorifics) so the same person mentioned by two sources is recognized as one candidate.
4. **Candidate resolver** — merges normalized results into 0..N candidate contacts per company; every field on a candidate carries the `source_url`(s) it came from (provenance).
5. **Confidence scorer** — scores each candidate 0-100 from the merged signals (see Quality).
6. **Decision gate** — applies the confidence threshold: below threshold → blank `contact_email_or_phone`, `needs_human_review = true`; at/above → pass through as-is.
7. **Output writer** — emits one row per input company with the required fields.

Each stage takes the previous stage's output and is independently testable; adapters are the only thing that needs mocking.

## Sources & strategy

Three independently-fallible source types (per the mocks):

- **registry** (business-registry lookup) — most authoritative for a *legal* owner/officer name + role, but frequently absent for small/unregistered businesses.
- **listing** (web/maps business listing) — usually just a general business phone, rarely a name+role; useful as corroboration or fallback.
- **enrichment** (email/phone enrichment) — most likely to produce a direct contact method, but comes with its own self-reported `provider_confidence` and can be a "plausible but unverified" guess.

Strategy: treat each source as a vote that contributes to one merged candidate. `registry` supplies identity (name + role) when present; `enrichment` supplies the contact method, weighted by its own confidence; `listing` corroborates (matching phone/name raises confidence) or serves as a fallback phone. Agreement across independent sources raises confidence; an isolated `enrichment` guess with nothing to corroborate it stays low.

## Quality

- **Dedupe**: normalize names (lowercase, strip punctuation/honorifics/whitespace) before comparing across sources. Two sources naming the "same" person (after normalization) merge into one candidate instead of two.
- **Confidence scoring** (0-100, additive, capped, explainable):
  - `+40` if `registry` returns a name + role (authoritative identity signal).
  - `+30` if `enrichment` returns an email/phone, scaled by `provider_confidence / 100` (e.g. provider_confidence 80 → `+24`).
  - `+15` if `listing` corroborates — its phone matches enrichment's phone, or its name (when present) matches registry's name.
  - `+15` "agreement bonus" if 2+ independent sources point at the same contact (same person and/or same phone/email).
  - Cap at 100; zero sources present → 0.
- **Provenance**: every emitted field carries the `source_url`(s) that produced it; `source` lists every provider that *contributed*, not just the winning one.
- **"Cannot verify"**: if the score is below threshold (or no provider returned anything), `contact_email_or_phone = ""` and `needs_human_review = true` — but if a name/role *was* found, it's still reported (at low confidence) so a human reviewer has a starting point. Never silently drop a partial finding, never fabricate a missing one.
- **False-positive risk**: the riskiest case is a single, uncorroborated `enrichment` guess with a low `provider_confidence` (e.g. 30-50). The formula above is tuned to keep that case below threshold rather than round it up — handing a rep a wrong email is worse than flagging the row for review.

## Privacy / compliance

**Will:**
- Use only business contact info (company-domain emails, business phone numbers).
- Record a `source_url` for every value, end to end.
- Design the record schema so a `suppressed`/opt-out flag could exclude a company from output before it ever reaches a human or downstream system.

**Will NOT:**
- Infer a person's identity, gender, or any protected characteristic from a name or address.
- Scrape live sites or call real APIs (mocks only, per this exercise).
- Output personal/home contact details, even if a source happens to surface one.
- Fabricate or "round up" a contact when sources disagree or are silent — disagreement and silence are both signals, not gaps to paper over.

## Clarifying questions

1. **Question: When sources disagree on *who* the contact is (e.g., registry says "Owner: Jane Doe" but enrichment found an email for "John Smith"), should we ever still emit one of them as the primary contact, or always degrade to `needs_human_review`?**
   - Why it matters: this is the single biggest lever on false positives — surfacing the "wrong but real" person is worse than surfacing nothing, but always degrading on any disagreement could tank recall on otherwise-decent data.
   - Default assumption: a name conflict between sources disqualifies the *contact method* (forces `needs_human_review = true`, blanks `contact_email_or_phone`), but the higher-priority role/name is still reported as `contact_name`/`contact_role` at low confidence so a reviewer has a lead.
   - What changes if answered: if conflicts should instead be resolved by a strict source-priority order (e.g., registry always wins identity; enrichment only ever supplies *that* person's contact method), the resolver drops the conflict-detection branch entirely and becomes a simple override hierarchy — simpler code, but a different (more confident) failure mode.

2. **Question: Should the confidence-score weights (the `+40/+30/+15/+15` above) be a configurable per-source table, or is an inline formula tuned to these three mocks acceptable for the slice?**
   - Why it matters: the formula only makes sense because we know these three mock shapes. A production system with 5-10 sources of varying reliability would need a swappable weight table rather than inline constants — but building that abstraction for 3 sources is over-engineering if this is purely illustrative.
   - Default assumption: a small `SOURCE_WEIGHTS` config dict (provider → base weight + how its self-reported confidence folds in), so the heuristic is swappable without touching the scoring logic — but no further abstraction (no plugin system, no per-source config files) for a 3-source slice.
   - What changes if answered: if illustrative-only, I'd inline the constants and spend the saved time on test coverage instead; if it needs to generalize toward production, I'd add a short doc on "how to add a new source" alongside the weight table.

3. **Question: For rows that land in `needs_human_review`, is a `review_reason` field (e.g. `no_sources`, `single_weak_source`, `identity_conflict`) useful in the output, beyond the boolean flag?**
   - Why it matters: at ~1,000 accounts, a reviewer's queue is far more actionable if pre-sorted by *why* — "nothing exists" (skip) vs "one weak signal" (quick manual check) vs "conflicting identities" (needs judgment) are three different workflows, not one undifferentiated pile.
   - Default assumption: I'll add `review_reason` as an extra, additive field — it doesn't break the spec'd schema and costs nothing extra since the scorer already knows why a row landed below threshold.
   - What changes if answered: if the output must match the spec'd columns exactly, I drop the field (or move it to a separate debug/log output); if it's wanted, I'd fix the reason taxonomy up front so it's a structured enum, not free text.
