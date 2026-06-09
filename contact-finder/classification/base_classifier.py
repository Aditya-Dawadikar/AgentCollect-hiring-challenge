"""Common interface for the v1 (rule-based) and v2 (decision-tree)
confidence classifiers -- both consume the TICKET-007 `signals` dict and
return the same shape, so `run.py` can swap one for the other."""

from abc import ABC, abstractmethod


class BaseClassifier(ABC):
    @abstractmethod
    def score(self, signals: dict) -> dict:
        """Returns {"confidence_score": int (0-100),
                     "classification": "high"|"medium"|"low"|"cannot_verify",
                     "needs_human_review": bool}"""
