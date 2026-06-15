# DOCUMENTATION.md — Enrichment Decision Criteria

This documents the decision logic implemented in
[`contact_finder.py`](contact_finder.py): how each of the three
mock providers (`registry`, `listing`, `enrichment`) is weighed, how
conflicts and agreements are detected, how `confidence_score` is computed,
and how the threshold gate decides `needs_human_review`. See
[`../PLAN.md`](../PLAN.md) for the original design rationale and
[`README.md`](README.md) for how the plan was adapted once real
mock shapes were known.

## 1. Pipeline

```
companies.csv ─┐
                ├─► resolve identity ─► resolve contact ─► agreement bonus ─► score
mocks.json ────┘                                                              │
                                                                 threshold gate ◄┘
                                                                        │
                                                                        ▼
                                                          output.json / output.csv
```

## 2. Identity resolution (`contact_name`, `contact_role`)

| `registry` | `listing` | Outcome |
|---|---|---|
| has `name` + `role` ≠ "Registered Agent" | any | identity = registry's name/role, base **+40** |
| has `name`, `role` == "Registered Agent" | any | identity = registry's name/role, base **+15** (registered agents are usually a third-party filing service, not company staff — see `notes`) |
| absent | has `name` | identity = listing's name (parenthetical role hint extracted, e.g. `"Jeff (manager)"` → name `"Jeff"`, role `"Manager"`), base **+20** |
| absent | absent / no name | identity empty (`""`), base **+0** |

**Conflict check** (only when both `registry.name` and `listing.name` are
present): names are normalized (lowercase, strip punctuation, drop
honorifics `dr/mr/mrs/ms/mx/prof`, drop parentheticals) and compared by
**surname (last token)**. `"Robert Kowalski"` vs `"Bob Kowalski"` →
surname `kowalski` matches → same person. `"Tina Alvarez"` vs
`"Marcus Webb"` → different surnames → **identity conflict**.

On conflict: the registry identity is still reported (higher authority per
clarifying question 1's default), the listing's conflicting name/role/url
is recorded in `notes`, and a **−20 conflict penalty** is applied to the
score.

## 3. Contact-method resolution (`contact_email_or_phone`)

| `enrichment` | `listing.phone` | Identity conflict? | Outcome |
|---|---|---|---|
| has `email` or `phone` | any | any | contact = enrichment's `email` (preferred) or `phone`, base **+30 × provider_confidence / 100** |
| absent | present | **No** | contact = listing's phone, base **+10** (generic business line, unverified) |
| absent | present | **Yes** | contact empty, base **+0** — a conflicting listing's phone belongs to the *other* (unconfirmed) person and is never attributed to the reported identity |
| absent | absent | any | contact empty, base **+0** |

## 4. Agreement / corroboration signals

Computed only when there is **no** identity conflict (a conflict already
zeroes the bonus — disagreement is not rewarded):

| Signal | Condition |
|---|---|
| `registry_listing_name_match` | `registry.name` and `listing.name` share a surname |
| `enrichment_listing_phone_match` | `enrichment.phone == listing.phone` (both non-null) |
| `enrichment_email_identity_match` | the local part of `enrichment.email` contains a first-name or surname token from the resolved identity (e.g. `d.ortega@…` ↔ "Daniel Ortega") |

| # signals found | Bonus |
|---|---|
| 0 | **+0** |
| 1 | **+15** |
| 2 or 3 | **+20** (capped — "multiple independent sources agree" is treated as uniformly strong) |

## 5. Confidence score

```
confidence_score = clamp(identity_base + contact_base + agreement_bonus − conflict_penalty, 0, 100)
```

`conflict_penalty` is **20** if the identity is in conflict, else **0**.
Rounded to the nearest integer.

## 6. Threshold gate → `needs_human_review`

Per `CLARIFICATIONS.md`, the cutoff is **70**:

```
needs_human_review = (confidence_score < 70) OR (resolved contact method is empty)
contact_email_or_phone = "" if needs_human_review else <resolved contact>
```

`contact_name` / `contact_role` are **always** reported when known — even
on `needs_human_review` rows — so a human reviewer has a lead. They are
never fabricated when unknown (both stay `""`).

## 7. `review_reason` (first match wins)

| Reason | Condition |
|---|---|
| `no_sources` | none of `registry`/`listing`/`enrichment` returned anything for this company |
| `identity_conflict` | registry and listing identified different people |
| `no_contact_method` | no enrichment and no usable listing phone (regardless of identity confidence) |
| `single_weak_source` | `confidence_score < 70` and **zero** agreement signals |
| `low_confidence` | `confidence_score < 70` with at least one agreement signal, still under threshold |
| *(empty)* | `confidence_score ≥ 70` and a contact method was found — no review needed |

## 8. Provenance

`provenance` maps each output field to the `source_url`(s) that produced
it. `source` lists **every** provider that returned non-empty data for the
company (what was checked), independent of which provider's value won —
full transparency even when a source was consulted but not used (e.g. a
conflicting listing).

## 9. Worked examples

| Company | identity | contact | agreements | conflict | score | review_reason |
|---|---|---|---|---|---|---|
| Cedar Ridge Plumbing LLC | +40 (registry, Owner) | +25.2 (enrichment, conf 84) | 2 → +20 | no | **85** | *(none)* |
| Pioneer Landscaping Inc | +40 (registry, President) | +26.4 (enrichment, conf 88) | 3 → +20 | no | **86** | *(none)* |
| Harbor Light Electric | +40 (registry, Owner) | +10 (listing phone, no enrichment) | 1 → +15 | no | **65** | `low_confidence` (just under threshold) |
| Lakeside Auto Glass | +20 (listing "Jeff", role "Manager") | +17.4 (enrichment, conf 58) | 1 → +15 | no | **52** | `low_confidence` |
| Coastal Breeze Pool Service | +40 (registry, "Tina Alvarez"/Manager) | +0 (listing phone discarded — belongs to "Marcus Webb") | 0 (conflict) | **yes** (−20) | **20** | `identity_conflict` |
| Northgate HVAC Services | +15 (registry, Registered Agent) | +0 (no enrichment/listing) | 0 | no | **15** | `no_contact_method` |
| Riverside Print & Sign | +0 (no identity found) | +12.3 (enrichment, conf 41) | 0 | no | **12** | `single_weak_source` |
| Redwood Cabinetry *(et al., 12 companies)* | +0 | +0 | 0 | no | **0** | `no_sources` |

## 10. Compliance guardrails reflected in the flow

- Never emits a contact value that isn't backed by at least one
  `source_url` (see `provenance`).
- Below-threshold rows return `contact_email_or_phone = ""` rather than a
  guessed value — no "rounding up" a weak signal into a usable contact.
- Identity conflicts degrade to `needs_human_review` instead of picking a
  contact method that might belong to the wrong person.
- All fields originate from business-context mock data (company name,
  registered-agent/officer names, business phone/email) — nothing in this
  flow infers or surfaces personal/home information.
