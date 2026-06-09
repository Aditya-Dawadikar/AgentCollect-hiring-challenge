# ADR-0003: Source authority, conflict definition, and candidate selection

**Status:** Accepted
**Ticket:** TICKET-007

## Context

`SignalFusionEngine.fuse()` must turn three independently-fallible provider
payloads (`registry`, `listing`, `enrichment`) into one `FusedContact`: a
single best-guess candidate (name, role, email, phone), per-field
provenance (`source_urls`), a `signals` dict for both classifiers, and a
list of `conflicts`.

Three design questions had to be settled:

1. When both `registry` and `listing` supply a `name`, which wins?
2. What counts as a "conflict" worth flagging?
3. How is `candidate_phone`/`candidate_email`/`candidate_name` chosen when
   sources disagree or are missing?

## Decision

### 1. Authority order: registry > listing

`registry` is the legal-ownership record (per `PLAN.md` "Sources &
strategy"); `listing` is a web/maps listing that can be stale or
crowd-edited. When both provide a name:

- If they fuzzy-match (`FuzzyNameMatcher`, threshold 85 — see ADR-0002),
  `candidate_name` = the **registry** name (normalized).
- If they do **not** fuzzy-match, `candidate_name` is *still* the registry
  name (registry remains authoritative), but the disagreement is recorded
  as a conflict (see below) so it surfaces in `signals["has_conflict"]` and
  ultimately lowers the confidence score.

`candidate_role` always comes from `registry` — across all 18 mock
companies, `role` is a registry-only field; `listing` and `enrichment`
never supply one. There is therefore nothing to arbitrate for role.

`config.settings.ROLE_PRIORITY` (the AP-manager > owner > CFO > office-manager
ranking from `CLARIFICATIONS.md`) is **not** consulted by `signal_fusion`:
with only one source ever supplying a role, there is no list to rank. It
remains in `settings` as a record of the target-persona priority from
`CLARIFICATIONS.md` and is available to later tickets (e.g. as a tie-breaker
if a future source adds role data), but `role_is_decision_maker` is
deliberately a simple binary signal (`role is not None and role.lower() not
in NON_DECISION_MAKER_ROLES`) rather than a ranked score, since a single
source can't disagree with itself.

### 2. Conflict definition: registry/listing name mismatch only

A `conflicts` entry is recorded **only** when both `registry.name` and
`listing.name` are present and `FuzzyNameMatcher.match()` returns `False`.
Phone and email differences are not modeled as "conflicts" — they're
resolved by simple precedence (see #3) because, unlike a person's identity,
having two different phone numbers for the same business isn't a sign one
of them is *wrong*.

`signals["has_conflict"] = len(conflicts) > 0`.

#### Known consequence: nicknames trigger "conflicts" too

Per ADR-0002, `"Robert Kowalski"` (registry) vs `"Bob Kowalski"` (listing) —
Ironclad Welding Shop — scores ~81, below the 85 threshold. By the rule
above this **is** recorded as a conflict, even though it's almost certainly
the same person under a nickname.

This was a deliberate choice, not an oversight: the alternative (a
hand-maintained nickname table to special-case "Robert"/"Bob") was rejected
in ADR-0002 as a maintenance burden that doesn't generalize. The downstream
effect is consistent with "precision over recall" (`CLARIFICATIONS.md`):
Ironclad Welding Shop ends up with `name_sources_agree=False`,
`has_conflict=True`, and — because `candidate_name` is the registry's
"Robert Kowalski" while the enrichment email is `bob@ironcladweld.com` —
`email_matches_name=False` too. Three signals point the same direction
(possible identity ambiguity), so both classifiers correctly produce a
lower confidence score for this company than for, say, Cedar Ridge Plumbing
(which agrees on every signal). A human reviewer sees "Robert Kowalski,
Owner" plus the conflict detail (`registry: "Robert Kowalski"`, `listing:
"Bob Kowalski"`) and can resolve it in seconds — which is exactly the
"needs_human_review" experience `CLARIFICATIONS.md` asks for.

### 3. Candidate field selection

| Field | Rule |
|---|---|
| `candidate_name` | `ConflictResolver.resolve()` result (registry > listing, normalized via `FuzzyNameMatcher.normalize`); else derived from a non-generic enrichment email (see below); else `None`. |
| `candidate_role` | `registry.role`, else `None`. |
| `candidate_email` | `enrichment.email`, else `None` — only `enrichment` ever supplies an email. |
| `candidate_phone` | `listing.phone`, else `enrichment.phone`, else `None`. Listing wins because it's typically the publicly-listed business line, which is what a collections call should dial first; `enrichment.phone` is a fallback when no listing exists (e.g. Greenfield Catering Group, Tidewater Plumbing & Heating). |

#### Email-derived name fallback

If `candidate_name` is still `None` after `ConflictResolver` but
`candidate_email` is present and **not** generic (`EmailMatcher.is_generic`
is `False`), derive a display name from
`EmailMatcher.name_tokens(candidate_email)` (e.g. `"jeff@example.com"` ->
`"Jeff"`), normalize it, and attribute `source_urls["name"]` to the
enrichment record.

**Correction to the original TICKET-007 draft:** the draft cited *Lakeside
Auto Glass* as the example for this fallback. Re-checking the actual mock
data: `listing.name = "Jeff (manager)"` **is** present for Lakeside Auto
Glass, so `candidate_name = "Jeff"` comes from `ConflictResolver` (via
`FuzzyNameMatcher.normalize` stripping the `"(manager)"` suffix), not from
the email fallback. `email_matches_name=True` still holds — it's now
corroboration between listing and enrichment rather than an email-only
derivation.

Across the full 18-company mock set, **no company actually exercises this
fallback** — every company with no registry/listing name either has a
generic enrichment email (`info@`, `office@`, `contact@`, `sales@`) or no
enrichment at all. The fallback is still implemented (cheap, and it's the
kind of "every bit of signal helps, but say so honestly" behavior the
challenge brief asks for) and is covered by
`tests/test_signal_fusion.py::test_email_derived_name_fallback`, which uses
a small stub `MockProviderClient`-shaped object with a synthetic
`"jeff@example.com"`-only payload.

### `source_urls` provenance

`source_urls` maps each populated candidate field (`name`, `role`, `email`,
`phone`) to the list of `source_url`s that supplied a *non-null* value for
that field — not just the one that "won". For `name`, that means both
`registry.source_url` and `listing.source_url` appear when both providers
named someone (even if they conflict, e.g. Coastal Breeze Pool Service),
giving a reviewer both data points to compare. For `phone`, both
`listing.source_url` and `enrichment.source_url` appear when both supplied
a phone (e.g. Pioneer Landscaping Inc, Sunbelt Roofing Co), which is also
how `phone_sources_agree` gets its provenance trail. A company with zero
matching providers (`Redwood Cabinetry`) gets `source_urls == {}`.

## Consequences

- `FusedContact.signals` has a fixed 13-key shape (enforced by
  `tests/test_signal_fusion.py::test_fuse_runs_for_every_company_without_error`,
  which runs `fuse()` over all 30 CSV rows including the 12 with zero mock
  data) — TICKET-008/009's `features.signals_to_vector` can rely on exactly
  these keys always being present.
- `conflicts` is a list of dicts (`field`/`registry`/`listing`/`reason`),
  always present (possibly empty) — TICKET-011's `formatter.build_reason`
  can iterate it unconditionally.
- The Ironclad Welding Shop "nickname conflict" is expected output, not a
  bug — TICKET-010's evaluation should not treat a `medium`/`low`
  classification for Ironclad as a model error.
