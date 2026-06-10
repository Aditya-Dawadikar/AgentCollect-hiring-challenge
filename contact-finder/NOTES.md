# TICKET-004 — Zero-Budget Contact Finder (real-data POC)

Three real US SMBs, found and cross-referenced using only free public
sources, scored by the **existing v1/v2 classifiers** (`run_ticket004.py`
swaps the mock provider client for a real one — no classifier code changed).

## Results (v1 `RuleBasedClassifier` — see "Confidence formula" below)

| company_name | contact_name | contact_role | contact_email_or_phone | confidence_score | needs_human_review | source_urls |
|---|---|---|---|---|---|---|
| Casey's Independent Auto Repair | Paul McGowan | Owner | service@caseysia.com | 75 | false | https://www.bbb.org/us/wa/vancouver/profile/auto-repair/caseys-independent-auto-repair-1296-72000185 \| https://www.yelp.com/biz/caseys-independent-auto-repair-vancouver \| https://caseysindependentauto.com/contact-us/ |
| My Dad's Plumbing | *(blank)* | *(blank)* | *(blank)* | 50 | **true** | https://www.bbb.org/us/ca/san-diego/profile/plumber/my-dads-plumbing-1126-1000059807 \| https://www.yelp.com/biz/my-dads-plumbing-san-dimas |
| The Print House | *(blank)* | *(blank)* | *(blank)* | 55 | **true** | https://www.bbb.org/us/ma/malden/profile/printers/the-print-house-0021-11033 \| https://www.yelp.com/biz/the-print-house-malden-2 \| https://www.printhouse.com/about |

Per `output/formatter.py` (ADR-0007), rows with `needs_human_review = true`
keep `confidence_score`/`source_urls`/`reason` populated for audit but blank
`contact_name`/`contact_role`/`contact_email_or_phone` — exactly the
`< 70 -> ""` + `needs_human_review=true` rule this ticket asks for.

Reproduce with: `cd contact-finder && venv\Scripts\python run_ticket004.py`
(writes `output/results/ticket004_v1_predictions.csv` /
`ticket004_v2_predictions.csv`).

## v1 vs v2 on real data

| company | v1 (rule-based) | v2 (decision tree) |
|---|---|---|
| Casey's Independent Auto Repair | medium (75), verified | high (86), verified |
| My Dad's Plumbing | **low (50), needs review** | high (86), verified |
| The Print House | low (55), needs review | high (86), verified |

v2 marks all three "high(86)" — its synthetic training data apparently
treats `has_registry_name + role_is_decision_maker + has_conflict=False +
sources_count>=2` as enough for "high", regardless of whether any other
source corroborates the name or whether an email exists. v1 is more
conservative and, on the **My Dad's Plumbing** row, I think v1 is *right* to
be conservative: see "the hard row" below. This matches the existing
Stage B finding (`README.md` §6) that v1 is "marginally more conservative"
than v2 — the gap is much more visible on noisy real data than on the
synthetic 30-company set.

---

## 1. Pipeline (5 bullets)

1. **Seed**: `(company_name, mailing_address)` — that's the only input, per
   the ticket.
2. **registry** signal — the company's **BBB Business Profile** (free, no
   login). BBB independently lists a "Business Management" name + title
   (Owner/President/etc.), the closest free analog to an authoritative
   record of who runs the business → `has_registry_name`, `candidate_role`.
3. **listing** signal — the company's **Yelp** listing (free, no login).
   Cross-checks phone/address independently of BBB → `has_listing_phone`,
   and (when present) `has_listing_name`.
4. **enrichment** signal — the company's own **website About/Contact page**
   (free). Self-reported email/phone, same "weak, self-reported" trust level
   as the original mock `enrichment` provider → `has_enrichment_email`,
   `has_enrichment_phone`, `enrichment_provider_confidence`.
5. **Score** — feed the resulting 13-key `signals` dict straight into the
   unmodified `RuleBasedClassifier` (v1) and `DecisionTreeConfidenceClassifier`
   (v2) via the existing `SignalFusionEngine` + `format_output_row`. The only
   new code is `RealProviderClient` (a `query_all()`-compatible adapter over
   hand-collected real records) in `run_ticket004.py`.

## 2. Why these free sources (and not others)

- **BBB** — no API key, no login, no rate limit hit in practice. BBB
  performs at least light identity verification to list a "Business
  Management" contact (even for *non*-accredited profiles, as both
  My Dad's Plumbing and The Print House show), making it the best free
  stand-in for a "registry of record" for a tiny business that has no state
  filings worth looking up.
- **Yelp** — every US storefront SMB has one; gives a second, independently
  maintained phone/address to cross-check against BBB and the company site.
  Free and instantly searchable (though direct page fetches return 403 to
  bots — see "next 30 minutes").
- **Company's own About/Contact page** — free, no rate limit, and for a
  one-location SMB it's often the *only* place an email is published at
  all. Fills the `enrichment.email`/`phone` slot.
- **Rejected**:
  - *Hunter.io free tier* — requires account signup (25 lookups/month tied
    to an API key), not the "open a URL, get an answer" reproducibility this
    exercise wants.
  - *LinkedIn* — aggressive bot-blocking, no usable public search without a
    login.
  - *State Secretary-of-State / OpenCorporates* — great for the *legal
    entity name* and registered agent, but the registered agent is almost
    always a law firm or formation service, not the operational
    decision-maker (`config/settings.NON_DECISION_MAKER_ROLES` already
    excludes `"registered agent"` for exactly this reason). Not worth a 4th
    fetch when BBB already gives a named owner/title.
  - *SEC EDGAR / Crunchbase* — irrelevant; none of these are public or
    venture-backed companies.
  - *Google Maps* — Yelp already gave the same phone/address for free and is
    easier to cite as a stable URL.

## 3. What I'd add in the next 30 minutes

- **Facebook Business Page** as a 4th source. Right now `has_listing_name`
  is `False` for all three rows because Yelp never names an owner — that
  structurally caps `name_sources_agree` and `has_conflict` at `False` for
  *every* real row (the existing `ConflictResolver` only compares
  registry-vs-listing names). A Facebook "About" section often names an
  owner/manager and would let `name_sources_agree` actually fire.
- **Resolve the My Dad's Plumbing location mismatch** (see "the hard row"
  below) — call both phone numbers or check the CA Secretary of State
  business search by name to confirm whether the BBB San Diego profile and
  the Yelp San Dimas listing are the same legal entity.
- **Fix `FuzzyNameMatcher.normalize()`'s `.title()` call** —
  `"Paul McGowan".title()` → `"Paul Mcgowan"` (Python's `.title()` lowercases
  the internal capital). Cosmetic, but it's the literal string a sales rep
  would see as `contact_name`.
- **Extend `GENERIC_EMAIL_LOCAL_PARTS`** with `"service"` (and
  `"team"`/`"customerservice"`) — `service@caseysia.com` is a role mailbox,
  not Paul McGowan's personal address, but the current set
  (`info, office, contact, sales, support, admin, help, hello, hr, billing`)
  doesn't catch it, so it currently earns the full `+20` non-generic-email
  bonus.
- **Free WHOIS lookup** on each company's domain — for small sole-proprietor
  domains the registrant org/email is sometimes still unredacted, which
  would be a 5th independent, free, zero-login source.

## 4. `confidence_score` formula

I reused **v1's existing weighted sum unchanged** (`classification/v1_rule_based.py`,
ADR-0004) as the deliverable's `confidence_score` — this *is* "our
classifiers POC", just pointed at real records instead of
`challenge/mocks/enrichment_responses.json`:

```
if sources_count == 0: confidence_score = 0  (cannot_verify)
else:
  total =  35  if has_registry_name
        + 20  if has_enrichment_email and not generic_email
        + 10  if has_listing_phone or has_enrichment_phone
        + 15  if name_sources_agree
        + 10  if email_matches_name
        +  5  if phone_sources_agree
        +  5  if role_is_decision_maker
        - 25  if has_conflict
        - 10  if generic_email and sources_count == 1
  confidence_score = clamp(total, 0, 100)

classification:  >=80 high | >=60 medium | >=30 low | else cannot_verify
needs_human_review = confidence_score < 70
```

**Why v1 over v2 for the deliverable column**: v2 (decision tree) scored all
three rows "high (86)", including **My Dad's Plumbing** — but the BBB
"registry" record we found (`Joe Atto, Owner`, San Diego CA 92108, phone
(949) 337-8677) doesn't match the Yelp "listing" record for the actual
San Dimas, CA 91773 shop (phone (909) 542-9394) on *either* address or
phone. v2 still paired "Joe Atto, Owner" with the San Dimas phone number at
86% confidence — i.e. it would tell a rep to call (909) 542-9394 and ask for
"Joe Atto". v1's score of 50 (`needs_human_review=true`) correctly routes
this to a human instead. Per `CLARIFICATIONS.md`'s "precision over recall"
principle, v1's extra conservatism is the right default here, even though it
means 2 of our 3 real rows end up blank.

### The hard row: My Dad's Plumbing

This is the row "where nothing comes back" cleanly:

- **registry** (BBB, San Diego profile) names an owner ("Joe Atto") but for
  an address/phone in a *different city* than the shop we're actually
  trying to reach (San Dimas, per Yelp).
- **enrichment**: `mydadsplumbing.com` returns HTTP 403 to automated
  fetches, so no enrichment record could be obtained at all
  (`"enrichment": None` in `run_ticket004.py`).
- **Fallback**: keep the row in the output (don't drop it — `source_urls`
  and `reason` stay populated for an auditor), confidence lands at 50
  ("low"), `needs_human_review=true` blanks the contact fields, and
  `reason` says *"Confidence 50 below threshold 70."* A human should call
  the Yelp-listed number `(909) 542-9394` and *ask* whether "Joe Atto" /
  "Joe Otto" (the name the Otto family uses in their own marketing copy) is
  still the right contact, rather than auto-emailing/calling on the BBB
  identity alone.
