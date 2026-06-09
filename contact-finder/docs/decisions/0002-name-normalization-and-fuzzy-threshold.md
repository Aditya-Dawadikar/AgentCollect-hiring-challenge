# ADR-0002: Name normalization rules and fuzzy-match threshold

**Status:** Accepted
**Ticket:** TICKET-006

## Context

The three mock providers (`registry`, `listing`, `enrichment`) describe the
same person in inconsistent formats:

- Honorifics: `"Dr. Emily Hart"` (registry) vs `"Emily Hart"` (listing) —
  Brookside Veterinary Clinic.
- Abbreviated first names: `"Sean Murphy"` (registry) vs `"S. Murphy"`
  (listing) — Harbor Light Electric.
- Parenthetical role annotations: `"Jeff (manager)"` (listing) — Lakeside
  Auto Glass.
- Punctuation differences: `"D. Ortega"` vs `"Daniel Ortega"`.
- Email local-parts that encode a name: `"d.ortega@cedarridgeplumbing.com"` →
  `"Daniel Ortega"`, `"karen@bayviewauto.com"` → `"Karen Liu"`.

`SignalFusionEngine` (TICKET-007) needs a single yes/no answer to "do these
two name strings refer to the same person?" to compute
`name_sources_agree` and `email_matches_name`.

## Decision

`FuzzyNameMatcher.normalize(name)`:

1. Strip any parenthetical suffix (`"Jeff (manager)"` -> `"Jeff"`) via
   `re.sub(r"\(.*?\)", "", name)`.
2. Replace `.` with a space (so `"S. Murphy"` -> `"S  Murphy"`, `"D.
   Ortega"` -> `"D  Ortega"`) and split into tokens.
3. Drop tokens that are honorifics (`dr`, `mr`, `mrs`, `ms`, `miss`, `prof`,
   case-insensitive).
4. Rejoin and title-case the result.

`FuzzyNameMatcher.score(name1, name2)` runs both names through `normalize`
and compares them with `fuzzywuzzy.fuzz.token_set_ratio`. `token_set_ratio`
(rather than `ratio` or `partial_ratio`) was chosen because it tokenizes
both strings, takes the set intersection/difference, and is therefore robust
to **missing tokens** (`"S Murphy"` vs `"Sean Murphy"`) and **token order**,
without being fooled by one string simply being a substring of the other
(which `partial_ratio` would score as 100 for almost any short alias).

`FuzzyNameMatcher.match(name1, name2)` returns `score >= threshold`, with
`threshold = settings.FUZZY_NAME_THRESHOLD = 85`.

`EmailMatcher.matches_name(email, name, name_matcher)` extracts the local
part of the email, splits on `.`, `_`, `-`, strips digits from each token
(so `"jeff2"` -> `"jeff"`), joins the remaining tokens with a space, and runs
that through the same `FuzzyNameMatcher.match`.

### Threshold = 85 — verification against real mock data

| Pair | After normalize | `token_set_ratio` | >= 85? |
|---|---|---|---|
| `"Sean Murphy"` / `"S. Murphy"` | `"Sean Murphy"` / `"S Murphy"` | 86 | yes |
| `"Dr. Emily Hart"` / `"Emily Hart"` | `"Emily Hart"` / `"Emily Hart"` | 100 | yes |
| `"Tina Alvarez"` / `"Marcus Webb"` | unchanged | ~24 | no (correct — different people) |
| `"d.ortega@cedarridgeplumbing.com"` tokens `"d ortega"` / `"Daniel Ortega"` | `"D Ortega"` / `"Daniel Ortega"` | 86 | yes |
| `"karen@bayviewauto.com"` tokens `"karen"` / `"Karen Liu"` | `"Karen"` / `"Karen Liu"` | 100 | yes |

A threshold of 85 is the lowest round value that accepts every true-positive
pair above while still rejecting the Coastal Breeze Pool Service conflict
(`"Tina Alvarez"` vs `"Marcus Webb"`, score ~24 — nowhere close, so the exact
threshold doesn't matter for that case but confirms there's no risk of a
false accept).

## Known limitation: nicknames

`"Robert Kowalski"` (registry) vs `"Bob Kowalski"` (listing) — Ironclad
Welding Shop — scores **~81**, just below the 85 threshold, so
`name_sources_agree` is `False` for this company even though both names
refer to the same person.

This is a known gap: pure string-similarity matching cannot bridge
nickname/given-name pairs (`Robert`/`Bob`, `William`/`Bill`, `Margaret`/
`Peg`) because the strings themselves share little structure. Closing this
gap would require a nickname-alias table (e.g. a static `Robert -> {Bob,
Rob, Bobby}` mapping) consulted before falling back to fuzzy scoring.

This was deliberately **not** added for Stage B:

- It only affects 1 of the 18 mock companies with data.
- A hardcoded English-nickname table is a maintenance burden and doesn't
  generalize (no coverage for non-English names).
- The system is explicitly "precision over recall": when
  `name_sources_agree` is `False`, the conflict resolver and classifier
  still produce a usable (if lower-confidence) result rather than a wrong
  one — `Ironclad Welding Shop` ends up as `medium`/`low` confidence rather
  than `high`, which is the correct conservative behavior given the
  ambiguity.

If this becomes a recurring problem in real data, the fix is additive: add
an alias-table lookup as a first check inside `FuzzyNameMatcher.match`
before falling back to `token_set_ratio`.

## Consequences

- `normalize()` is deliberately aggressive about stripping noise
  (honorifics, parentheticals, punctuation) because the inputs are
  short, structured "person name" strings, not free text — there's no risk
  of stripping meaningful content.
- `EmailMatcher.matches_name` depends on `FuzzyNameMatcher`, creating a
  one-way dependency `email_matcher -> fuzzy_matcher` (not the reverse).
- The Robert/Bob Kowalski case will surface in TICKET-007's signal-fusion
  output and TICKET-010's evaluation as a `name_sources_agree=False` /
  lower-confidence result. This is expected and is not a bug to "fix" in
  later tickets.
