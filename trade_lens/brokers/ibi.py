from __future__ import annotations

from enum import Enum
from typing import Sequence

import pandas as pd


class RawDataAttribute(Enum):
    ACTION_DATE = "action_date"
    ACTION_TYPE = "action_type"
    PAPER_NAME = "paper_name"
    PAPER_SYMBOL = "paper_symbol"
    QUANTITY = "quantity"
    EXECUTION_PRICE = "execution_price"
    CURRENCY = "currency"
    COMMISSION_FEE = "commission_fee"
    ADDITIONAL_FEES = "additional_fees"
    TOTAL_VALUE_FOREIGN = "total_value_foreign"  # USD in your v1 assumption
    TOTAL_VALUE_SHEKEL = "total_value_shekel"
    SHEKEL_BALANCE = "shekel_balance"
    ESTIMATED_CAPITAL_GAINS_TAX = "estimated_capital_gains_tax"


HEBREW_COLUMNS_MAP = {
    "תאריך": RawDataAttribute.ACTION_DATE.value,
    "סוג פעולה": RawDataAttribute.ACTION_TYPE.value,
    "שם נייר": RawDataAttribute.PAPER_NAME.value,
    "מס' נייר / סימבול": RawDataAttribute.PAPER_SYMBOL.value,
    "כמות": RawDataAttribute.QUANTITY.value,
    "שער ביצוע": RawDataAttribute.EXECUTION_PRICE.value,
    "מטבע": RawDataAttribute.CURRENCY.value,
    "עמלת פעולה": RawDataAttribute.COMMISSION_FEE.value,
    "עמלות נלוות": RawDataAttribute.ADDITIONAL_FEES.value,
    'תמורה במט"ח': RawDataAttribute.TOTAL_VALUE_FOREIGN.value,
    "תמורה בשקלים": RawDataAttribute.TOTAL_VALUE_SHEKEL.value,
    "יתרה שקלית": RawDataAttribute.SHEKEL_BALANCE.value,
    "אומדן מס רווחי הון": RawDataAttribute.ESTIMATED_CAPITAL_GAINS_TAX.value,
}


class RawActionType(Enum):
    SALE_SHEKEL = "sale_shekel"
    WITHDRAWAL_TAX_FOREIGN = "withdrawal_tax_foreign"
    DEPOSIT_DIVIDEND_FOREIGN = "deposit_dividend_foreign"
    FUTURES_TAX = "futures_tax"
    TAX_SHIELD_ACCRUAL = "tax_shield_accrual"
    TAX_SHIELD_RESET = "tax_shield_reset"
    TAX_PAYABLE = "tax_payable"
    TAX_PAYMENT = "tax_payment"
    TAX_CREDIT = "tax_credit"
    BUY = "buy"
    DEPOSIT = "deposit"
    CASH_DEPOSIT = "cash_deposit"
    SELL = "sell"
    ACCOUNT_MAINTENANCE_FEE = "account_maintenance_fee"
    PURCHASE_SHEKEL = "purchase_shekel"
    WITHDRAWAL = "withdrawal"
    WITHDRAWAL_INTEREST_FOREIGN = "withdrawal_interest_foreign"
    OTHER_CASH = "other_cash"


HEBREW_ACTION_TYPE_MAP = {
    "מכירה שח": RawActionType.SALE_SHEKEL.value,
    "משיכת מס חול מטח": RawActionType.WITHDRAWAL_TAX_FOREIGN.value,
    "הפקדה דיבידנד מטח": RawActionType.DEPOSIT_DIVIDEND_FOREIGN.value,
    "מס עתידי": RawActionType.FUTURES_TAX.value,
    "איפוס מגן מס": RawActionType.TAX_SHIELD_RESET.value,
    "מגן מס": RawActionType.TAX_SHIELD_ACCRUAL.value,
    "מס לשלם": RawActionType.TAX_PAYABLE.value,
    "מס ששולם": RawActionType.TAX_PAYMENT.value,
    "זיכוי מס": RawActionType.TAX_CREDIT.value,
    "קניה חול מטח": RawActionType.BUY.value,
    "הפקדה": RawActionType.DEPOSIT.value,
    "מכירה חול מטח": RawActionType.SELL.value,
    "קניה שח": RawActionType.PURCHASE_SHEKEL.value,
    "העברה מזומן בשח": RawActionType.CASH_DEPOSIT.value,
    "דמי טפול מזומן בשח": RawActionType.ACCOUNT_MAINTENANCE_FEE.value,
    "משיכה": RawActionType.WITHDRAWAL.value,
    "משיכת ריבית מטח": RawActionType.WITHDRAWAL_INTEREST_FOREIGN.value,
    "שונות מזומן בשח": RawActionType.OTHER_CASH.value,
}


class IbiRawLoader:
    """Load IBI Excel exports (.xlsx) and normalize Hebrew columns to internal names."""

    def __init__(self, paths: str | Sequence[str]) -> None:
        self.paths = [paths] if isinstance(paths, str) else list(paths)
        if not self.paths:
            raise ValueError("At least one resource path is required.")
        self.df: pd.DataFrame | None = None

    def _load_single(self, path: str) -> pd.DataFrame:
        df = pd.read_excel(path)
        df.rename(columns=HEBREW_COLUMNS_MAP, inplace=True)
        if RawDataAttribute.ACTION_TYPE.value in df.columns:
            action_col = RawDataAttribute.ACTION_TYPE.value
            df[action_col] = df[action_col].astype("string").str.strip().map(HEBREW_ACTION_TYPE_MAP)
        return df

    def load(self) -> pd.DataFrame:
        frames = [self._load_single(path) for path in self.paths]
        self.df = pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]

        date_col = RawDataAttribute.ACTION_DATE.value
        if date_col in self.df.columns:
            self.df[date_col] = pd.to_datetime(self.df[date_col], dayfirst=True, errors="coerce")
            self.df.sort_values(by=date_col, inplace=True, kind="mergesort", na_position="last")
            self.df.reset_index(drop=True, inplace=True)

        return self.df


__all__ = [
    "RawDataAttribute",
    "RawActionType",
    "HEBREW_COLUMNS_MAP",
    "HEBREW_ACTION_TYPE_MAP",
    "IbiRawLoader",
]