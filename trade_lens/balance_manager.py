from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from trade_lens.action import Action, Deposit, Conversion, Transaction, Currency


class BalanceManager:
    """Maintain USD and ILS balances and apply actions.

    Supports deposits and conversions; other action types raise
    ``TypeError``.  Balances are simple floats and currencies are
    represented by :class:`~trade_lens.action.Currency` values.
    """

    def __init__(self) -> None:
        self.usd_balance: float = 0.0
        self.shekel_balance: float = 0.0

    def process_deposit(self, deposit: "Deposit") -> "BalanceManager":
        # ensure we have an enum regardless of whether caller passed a
        # string or the Currency member itself.
        cur = deposit.currency
        if isinstance(cur, str):
            cur = Currency(cur.upper())

        if cur == Currency.USD:
            self.usd_balance += deposit.quantity
        elif cur == Currency.ILS:
            self.shekel_balance += deposit.quantity
        else:
            raise ValueError(f"unsupported currency {deposit.currency!r}")
        return self

    def process_conversion(self, conv: "Conversion") -> "BalanceManager":
        src = conv.from_currency
        tgt = conv.to_currency
        # convert strings to enum if necessary
        if isinstance(src, str):
            src = Currency(src.upper())
        if isinstance(tgt, str):
            tgt = Currency(tgt.upper())

        if src not in (Currency.USD, Currency.ILS) or tgt not in (Currency.USD, Currency.ILS):
            raise ValueError("conversion only supports USD <-> ILS")

        amt = conv.amount
        rate = conv.rate

        if src == tgt:
            # nothing to do
            return self

        if src == Currency.USD:
            if self.usd_balance < amt:
                raise ValueError("insufficient USD balance")
            self.usd_balance -= amt
            self.shekel_balance += amt * rate
        else:  # src == Currency.ILS
            if self.shekel_balance < amt:
                raise ValueError("insufficient ILS balance")
            self.shekel_balance -= amt
            self.usd_balance += amt * rate

        return self
    
    def process_transaction(self, txn: "Transaction") -> "BalanceManager":
        cur = txn.currency
        if isinstance(cur, str):
            cur = Currency(cur.upper())
        if cur not in (Currency.USD, Currency.ILS):
            raise ValueError(f"unsupported currency {txn.currency!r}")
        
        total_cost = txn.quantity * txn.price
        
        if txn.txn_type.lower() == "buy":
            if cur == Currency.USD:
                if self.usd_balance < total_cost:
                    raise ValueError("insufficient USD balance")
                self.usd_balance -= total_cost
            else:  # Currency.ILS
                if self.shekel_balance < total_cost:
                    raise ValueError("insufficient ILS balance")
                self.shekel_balance -= total_cost
        elif txn.txn_type.lower() == "sell":
            if cur == Currency.USD:
                self.usd_balance += total_cost
            else:  # Currency.ILS
                self.shekel_balance += total_cost
        else:
            raise ValueError(f"unsupported transaction type {txn.txn_type!r}")
        
        return self

    def process_action(self, action: "Action") -> "BalanceManager":
        if isinstance(action, Deposit):
            print(action)
            return self.process_deposit(action)
        elif isinstance(action, Conversion):
            return self.process_conversion(action)
        elif isinstance(action, Transaction):
            # Transaction handling can be added here if needed
            return self
        else:
            raise TypeError(f"unsupported action type {type(action).__name__!r}")

    def __repr__(self) -> str:
        return f"<BalanceManager usd={self.usd_balance:.2f} ILS={self.shekel_balance:.2f}>"
    __str__ = __repr__


__all__ = ["BalanceManager"]

# simple CLI driver for interactive experimentation
def _main() -> None:
    # demo BalanceManager
    bm = BalanceManager()
    try:
        bm.process_deposit(Deposit(date=date(2025, 4, 1), currency=Currency.USD, quantity=500))
        bm.process_deposit(Deposit(date=date(2025, 4, 2), currency=Currency.ILS, quantity=1000))
        print("after deposits:", bm)

        conv = Conversion(
            date=date(2025, 4, 3),
            from_currency=Currency.USD,
            to_currency=Currency.ILS,
            amount=200,
            rate=3.5,
        )
        bm.process_conversion(conv)
        print("after conversion:", bm)

        act = Conversion(
                date=date(2025, 4, 4),
                from_currency=Currency.ILS,
                to_currency=Currency.USD,
                amount=100,
                rate=0.28,
            )
        # using the dispatcher
        bm.process_action(
            act
        )
        print("after reverse conversion:", bm)
    except Exception as exc:  # noqa: BLE001
        print("error processing action:", exc)

if __name__ == "__main__":
    _main()