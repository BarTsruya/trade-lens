from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from datetime import date

from .enums import Currency


@dataclass
class Action(ABC):
    date: date


@dataclass
class Transaction(Action):
    txn_type: str  # "buy"/"sell"
    currency: Currency
    quantity: float
    price: float
    symbol: str | None = None


@dataclass
class Deposit(Action):
    currency: Currency
    quantity: float


@dataclass
class Conversion(Action):
    from_currency: Currency
    to_currency: Currency
    amount: float
    rate: float

    def __post_init__(self):
        if isinstance(self.from_currency, str):
            self.from_currency = Currency(self.from_currency.upper())
        if isinstance(self.to_currency, str):
            self.to_currency = Currency(self.to_currency.upper())


__all__ = ["Action", "Transaction", "Deposit", "Conversion"]