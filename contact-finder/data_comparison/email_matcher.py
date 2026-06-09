"""Email normalization, generic-mailbox detection, and email-to-name matching."""

import re

from config import settings
from data_comparison.base_strategy import BaseMatcher
from data_comparison.fuzzy_matcher import FuzzyNameMatcher

_LOCAL_PART_SPLIT = re.compile(r"[._\-]")
_DIGITS = re.compile(r"\d+")


class EmailMatcher(BaseMatcher):
    def normalize(self, email: str | None) -> str:
        if not email:
            return ""
        return email.strip().lower()

    def _local_part_tokens(self, email: str | None) -> list[str]:
        normalized = self.normalize(email)
        if "@" not in normalized:
            return []
        local = normalized.split("@", 1)[0]
        return [tok for tok in _LOCAL_PART_SPLIT.split(local) if tok]

    def is_generic(self, email: str | None) -> bool:
        return any(
            tok in settings.GENERIC_EMAIL_LOCAL_PARTS
            for tok in self._local_part_tokens(email)
        )

    def name_tokens(self, email: str | None) -> list[str]:
        return [_DIGITS.sub("", tok) for tok in self._local_part_tokens(email)]

    def matches_name(self, email: str | None, name: str | None,
                      name_matcher: FuzzyNameMatcher) -> bool:
        if not email or not name:
            return False
        tokens = [tok for tok in self.name_tokens(email) if tok]
        if not tokens:
            return False
        return name_matcher.match(" ".join(tokens), name)

    def match(self, email1: str | None, email2: str | None) -> bool:
        n1, n2 = self.normalize(email1), self.normalize(email2)
        if not n1 or not n2:
            return False
        return n1 == n2
