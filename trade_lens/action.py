from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from datetime import date
from enum import Enum


class Currency(Enum):
    """Supported currencies.

    ``value`` is the three‑letter ISO code; use ``.symbol`` if you need a
    user‑friendly glyph.
    """

    USD = "USD"
    ILS = "ILS"

    @property
    def symbol(self) -> str:
        return {Currency.USD: "$", Currency.ILS: "₪"}[self]


@dataclass
class Action(ABC):
    """Abstract base class for anything that happens on a particular
    date.

    Subclasses represent concrete activity: a transaction (buy/sell) or
    a deposit.  Having a common parent makes it easier to annotate
    collections of mixed actions later on.
    """

    date: date


@dataclass
class Transaction(Action):
    """A buy or sell of a security at a given price.

    ``txn_type`` is expected to be one of ``"buy"`` or ``"sell"``
    (plain strings for now, could be an ``Enum`` later).  ``price`` is
    the per-unit execution price.
    """

    txn_type: str  # "buy" or "sell"
    currency: Currency
    quantity: float
    price: float


@dataclass
class Deposit(Action):
    """A deposit of funds into the account.

    Deposits currently only carry a currency and quantity; other details
    can be added later if required.
    """

    currency: Currency
    quantity: float


@dataclass
class Conversion(Action):
    """A currency conversion.

    Represent converting ``amount`` units of ``from_currency`` to
    ``to_currency``.  ``rate`` is expressed as the amount of
    ``to_currency`` obtained per one unit of ``from_currency``.
    Only USD and ILS are supported; currencies are automatically
    uppercased.
    """

    from_currency: Currency
    to_currency: Currency
    amount: float
    rate: float

    def __post_init__(self):
        # convert strings to enum if necessary; preserve Currency instances
        if isinstance(self.from_currency, str):
            self.from_currency = Currency(self.from_currency.upper())
        if isinstance(self.to_currency, str):
            self.to_currency = Currency(self.to_currency.upper())

__all__ = ["Action", "Currency", "Transaction", "Deposit", "Conversion"]


# simple CLI driver for interactive experimentation
def _main() -> None:
    from datetime import date

    t1 = Transaction(
        date=date(2025, 1, 1),
        txn_type="buy",
        currency=Currency.USD,
        quantity=100,
        price=10.0,
    )
    t2 = Transaction(
        date=date(2025, 2, 1),
        txn_type="sell",
        currency=Currency.USD,
        quantity=50,
        price=12.5,
    )
    d1 = Deposit(date=date(2025, 3, 1), currency=Currency.USD, quantity=200)

    print(t1)
    print(t2)
    print(d1)


if __name__ == "__main__":
    _main()
