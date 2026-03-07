from __future__ import annotations

from enum import Enum


class Currency(Enum):
    USD = "USD"
    ILS = "ILS"

    @property
    def symbol(self) -> str:
        return {Currency.USD: "$", Currency.ILS: "₪"}[self]


__all__ = ["Currency"]