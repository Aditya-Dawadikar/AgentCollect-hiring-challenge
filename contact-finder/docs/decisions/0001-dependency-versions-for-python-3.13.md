# ADR-0001: Dependency versions for Python 3.13

**Status:** Accepted
**Ticket:** TICKET-005

## Context

The Stage B build plan (`INSTRUCTIONS.md`) specifies an exact
`requirements.txt`:

```
pandas==2.0.3
numpy==1.24.3
scikit-learn==1.3.0
fuzzywuzzy==0.18.0
python-Levenshtein==0.21.0
```

The development machine has Python 3.13.1. `pandas==2.0.3`,
`numpy==1.24.3`, `scikit-learn==1.3.0`, and `python-Levenshtein==0.21.0`
predate Python 3.13 (released Oct 2024) and ship no `cp313` wheels, which
would force a from-source build requiring a C/C++ toolchain on Windows.

## Decision

Use the latest stable releases of each library that install cleanly via
prebuilt wheels on Python 3.13, pinned to the exact versions verified to
install and pass the test suite:

```
pandas==3.0.3
numpy==2.4.6
scikit-learn==1.9.0
fuzzywuzzy==0.18.0
python-Levenshtein==0.27.3
pytest==9.0.3
```

`fuzzywuzzy==0.18.0` is unchanged (pure Python, version-agnostic) and is
kept because it's explicitly named in the build plan and `INSTRUCTIONS.md`'s
own `FuzzyNameMatcher` example is written against its API
(`fuzz.token_set_ratio`).

## Consequences

- API surface used by this project (`pandas.DataFrame`/`read_csv`,
  `fuzzywuzzy.fuzz`, `sklearn.tree.DecisionTreeClassifier`) is stable across
  these major versions, so no code changes are needed beyond what's written
  against the documented APIs.
- If this project is ever run on an older Python (<=3.11), these pins can be
  relaxed back toward the original `requirements.txt` versions; nothing in
  the code depends on a pandas/numpy/scikit-learn 3.x/2.x/1.9-only feature.
- `python-Levenshtein` installs successfully here (wheel available for
  cp313), so `fuzzywuzzy` gets its fast C-backed `Levenshtein` implementation
  with no extra `rapidfuzz` dependency.
