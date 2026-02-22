"""Top-level package for the TradeLens library.

This module primarily exists to mark ``trade_lens`` as a package so it
can be installed with pip and to expose a small public API surface for
convenience.
"""

from .action import Action, Transaction, Deposit, Conversion
from .balance_manager import BalanceManager
from .raw_data import RawDataLoader, RawActionType, RawDataAttribute


__all__ = [
    "Action",
    "Transaction",
    "Deposit",
    "Conversion",
    "BalanceManager",
    "RawDataLoader",
    "RawActionType",
    "RawDataAttribute",
]
