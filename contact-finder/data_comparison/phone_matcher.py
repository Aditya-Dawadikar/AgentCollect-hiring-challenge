"""Phone number normalization and matching."""

import re

from data_comparison.base_strategy import BaseMatcher

_NON_DIGIT = re.compile(r"\D")


class PhoneMatcher(BaseMatcher):
    def normalize(self, phone: str | None) -> str:
        if not phone:
            return ""
        digits = _NON_DIGIT.sub("", phone)
        if len(digits) == 11 and digits.startswith("1"):
            digits = digits[1:]
        return digits

    def match(self, phone1: str | None, phone2: str | None) -> bool:
        n1, n2 = self.normalize(phone1), self.normalize(phone2)
        if not n1 or not n2:
            return False
        return n1 == n2
