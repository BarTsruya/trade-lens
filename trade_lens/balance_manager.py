from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from trade_lens.action import Deposit, Conversion, Transaction


class BalanceManager:
    """Maintain USD and ILS balances and apply actions.

    Supports deposits and conversions; other action types raise
    ``TypeError``.  Balances are simple floats and currency codes are
    expected to be uppercase ``'USD'`` or ``'ILS'``.
    """

    def __init__(self) -> None:
        self.usd_balance: float = 0.0
        self.shekel_balance: float = 0.0

    def process_deposit(self, deposit: "Deposit") -> "BalanceManager":
        cur = deposit.currency.upper()
        if cur == "USD":
            self.usd_balance += deposit.quantity
        elif cur == "ILS":
            self.shekel_balance += deposit.quantity
        else:
            raise ValueError(f"unsupported currency {deposit.currency!r}")
        return self

    def process_conversion(self, conv: "Conversion") -> "BalanceManager":
        src = conv.from_currency.upper()
        tgt = conv.to_currency.upper()
        if src not in ("USD", "ILS") or tgt not in ("USD", "ILS"):
            raise ValueError("conversion only supports USD <-> ILS")

        amt = conv.amount
        rate = conv.rate

        if src == tgt:
            # nothing to do
            return self

        if src == "USD":
            if self.usd_balance < amt:
                raise ValueError("insufficient USD balance")
            self.usd_balance -= amt
            self.shekel_balance += amt * rate
        else:  # src == "ILS"
            if self.shekel_balance < amt:
                raise ValueError("insufficient ILS balance")
            self.shekel_balance -= amt
            self.usd_balance += amt * rate

        return self
    
    def process_transaction(self, txn: "Transaction") -> "BalanceManager":
        cur = txn.currency.upper()
        if cur not in ("USD", "ILS"):
            raise ValueError(f"unsupported currency {txn.currency!r}")
        
        total_cost = txn.quantity * txn.price
        
        if txn.txn_type.lower() == "buy":
            if cur == "USD":
                if self.usd_balance < total_cost:
                    raise ValueError("insufficient USD balance")
                self.usd_balance -= total_cost
            else:  # ILS
                if self.shekel_balance < total_cost:
                    raise ValueError("insufficient ILS balance")
                self.shekel_balance -= total_cost
        elif txn.txn_type.lower() == "sell":
            if cur == "USD":
                self.usd_balance += total_cost
            else:  # ILS
                self.shekel_balance += total_cost
        else:
            raise ValueError(f"unsupported transaction type {txn.txn_type!r}")
        
        return self

    def process_action(self, action: "Action") -> "BalanceManager":
        if isinstance(action, Deposit):
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
        bm.process_deposit(Deposit(date=date(2025, 4, 1), currency="USD", quantity=500))
        bm.process_deposit(Deposit(date=date(2025, 4, 2), currency="ILS", quantity=1000))
        print("after deposits:", bm)

        conv = Conversion(
            date=date(2025, 4, 3),
            from_currency="USD",
            to_currency="ILS",
            amount=200,
            rate=3.5,
        )
        bm.process_conversion(conv)
        print("after conversion:", bm)

        act = Conversion(
                date=date(2025, 4, 4),
                from_currency="ILS",
                to_currency="USD",
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