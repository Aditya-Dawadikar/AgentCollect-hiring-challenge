"""Name matching: "Daniel Ortega" vs "D. Ortega", "Sean Murphy" vs "S. Murphy".

Names from different providers carry honorifics ("Dr. Emily Hart"),
abbreviations ("S. Murphy"), and parenthetical role notes ("Jeff
(manager)"). normalize() strips that noise so fuzzywuzzy's
token_set_ratio can compare the actual name tokens.
"""

import re

from fuzzywuzzy import fuzz

from config import settings
from data_comparison.base_strategy import BaseMatcher

HONORIFICS = {"dr", "mr", "mrs", "ms", "miss", "prof"}


class FuzzyNameMatcher(BaseMatcher):
    def __init__(self, threshold: int = settings.FUZZY_NAME_THRESHOLD):
        self.threshold = threshold

    def normalize(self, name: str | None) -> str:
        if not name:
            return ""
        name = re.sub(r"\(.*?\)", "", name)
        tokens = [
            tok for tok in name.replace(".", " ").split()
            if tok.lower() not in HONORIFICS
        ]
        return " ".join(tokens).strip().title()

    def score(self, name1: str | None, name2: str | None) -> int:
        n1, n2 = self.normalize(name1), self.normalize(name2)
        if not n1 or not n2:
            return 0
        return fuzz.token_set_ratio(n1, n2)

    def match(self, name1: str | None, name2: str | None) -> bool:
        return self.score(name1, name2) >= self.threshold
