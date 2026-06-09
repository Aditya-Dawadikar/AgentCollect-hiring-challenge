"""Common interface for the data-comparison matching strategies."""

from abc import ABC, abstractmethod


class BaseMatcher(ABC):
    @abstractmethod
    def match(self, a, b) -> bool:
        """Returns True if `a` and `b` refer to the same underlying value
        (name, email, or phone number)."""
