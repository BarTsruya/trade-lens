from __future__ import annotations

from enum import Enum

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
    RAW_USD_AMOUNT = "raw_usd_amount"
    RAW_ILS_AMOUNT = "raw_ils_amount"
    ILS_BALANCE = "ils_balance"
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
    'תמורה במט"ח': RawDataAttribute.RAW_USD_AMOUNT.value,
    "תמורה בשקלים": RawDataAttribute.RAW_ILS_AMOUNT.value,
    "יתרה שקלית": RawDataAttribute.ILS_BALANCE.value,
    "אומדן מס רווחי הון": RawDataAttribute.ESTIMATED_CAPITAL_GAINS_TAX.value,
}


class RawActionType(Enum):
    DIVIDEND_TAX = "dividend_tax"
    DIVIDEND_DEPOSIT = "dividend_deposit"
    FUTURES_TAX = "futures_tax"
    TAX_SHIELD_ACCRUAL = "tax_shield_accrual"
    TAX_SHIELD_RESET = "tax_shield_reset"
    TAX_PAYABLE = "tax_payable"
    TAX_PAYMENT = "tax_payment"
    TAX_CREDIT = "tax_credit"
    BUY = "buy"
    CASH_DEPOSIT = "cash_deposit"
    SELL = "sell"
    ACCOUNT_MAINTENANCE_FEE = "account_maintenance_fee"
    FX_CONVERSION = "fx_conversion"
    DEBIT_INTEREST = "debit_interest"
    OTHER_CASH = "other_cash"


HEBREW_ACTION_TYPE_MAP = {
    "משיכת מס חול מטח": RawActionType.DIVIDEND_TAX.value,
    "הפקדה דיבידנד מטח": RawActionType.DIVIDEND_DEPOSIT.value,
    "מס עתידי": RawActionType.FUTURES_TAX.value,
    "איפוס מגן מס": RawActionType.TAX_SHIELD_RESET.value,
    "מגן מס": RawActionType.TAX_SHIELD_ACCRUAL.value,
    "מס לשלם": RawActionType.TAX_PAYABLE.value,
    "מס ששולם": RawActionType.TAX_PAYMENT.value,
    "זיכוי מס": RawActionType.TAX_CREDIT.value,
    "קניה חול מטח": RawActionType.BUY.value,
    "מכירה חול מטח": RawActionType.SELL.value,
    "קניה שח": RawActionType.FX_CONVERSION.value,
    "העברה מזומן בשח": RawActionType.CASH_DEPOSIT.value,
    "דמי טפול מזומן בשח": RawActionType.ACCOUNT_MAINTENANCE_FEE.value,
    "משיכת ריבית מטח": RawActionType.DEBIT_INTEREST.value,
    "שונות מזומן בשח": RawActionType.OTHER_CASH.value,
}


def load_single(path: str) -> pd.DataFrame:
    """Load one IBI Excel export (.xlsx) and normalize Hebrew columns to internal names."""
    df = pd.read_excel(path)
    df.rename(columns=HEBREW_COLUMNS_MAP, inplace=True)
    if RawDataAttribute.ACTION_TYPE.value in df.columns:
        action_col = RawDataAttribute.ACTION_TYPE.value
        raw_strings = df[action_col].astype("string").str.strip()
        df["_raw_action_type"] = raw_strings
        df[action_col] = raw_strings.map(HEBREW_ACTION_TYPE_MAP)
    return df


__all__ = [
    "RawDataAttribute",
    "RawActionType",
    "HEBREW_COLUMNS_MAP",
    "HEBREW_ACTION_TYPE_MAP",
    "load_single",
]