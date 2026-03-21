from __future__ import annotations

import io
from enum import Enum
from typing import Union

import pandas as pd

from trade_lens.brokers.base import BrokerLoader


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
    "הפקדה": RawActionType.CASH_DEPOSIT.value,
    "העברה מזומן בשח": RawActionType.CASH_DEPOSIT.value,
    "דמי טפול מזומן בשח": RawActionType.ACCOUNT_MAINTENANCE_FEE.value,
    "משיכת ריבית מטח": RawActionType.DEBIT_INTEREST.value,
    "שונות מזומן בשח": RawActionType.OTHER_CASH.value,
}


_BUY_SELL_ACTIONS = {RawActionType.BUY.value, RawActionType.SELL.value}


def load_single(source: Union[str, io.IOBase]) -> pd.DataFrame:
    """Load one IBI Excel export (.xlsx) and normalize Hebrew columns to internal names."""
    df = pd.read_excel(source)
    df.rename(columns=HEBREW_COLUMNS_MAP, inplace=True)
    if RawDataAttribute.ACTION_TYPE.value in df.columns:
        action_col = RawDataAttribute.ACTION_TYPE.value
        raw_strings = df[action_col].astype("string").str.strip()
        df["_raw_action_type"] = raw_strings
        df[action_col] = raw_strings.map(HEBREW_ACTION_TYPE_MAP)
    return df


class IBILoader(BrokerLoader):
    """Broker loader for IBI (Interactive Brokers Israel) Excel exports."""

    broker_id = "ibi"

    def load_raw(self, source: Union[str, bytes, io.IOBase]) -> pd.DataFrame:
        if isinstance(source, bytes):
            source = io.BytesIO(source)
        return load_single(source)

    def normalize(self, raw_df: pd.DataFrame) -> pd.DataFrame:  # noqa: C901
        """Transform an IBI raw DataFrame into the canonical ledger schema."""
        df = raw_df.copy()

        date_col = RawDataAttribute.ACTION_DATE.value
        action_col = RawDataAttribute.ACTION_TYPE.value
        symbol_col = RawDataAttribute.PAPER_SYMBOL.value
        paper_name_col = RawDataAttribute.PAPER_NAME.value
        quantity_col = RawDataAttribute.QUANTITY.value
        execution_price_col = RawDataAttribute.EXECUTION_PRICE.value
        estimated_tax_col = RawDataAttribute.ESTIMATED_CAPITAL_GAINS_TAX.value
        ils_balance_col = RawDataAttribute.ILS_BALANCE.value
        currency_col = RawDataAttribute.CURRENCY.value
        raw_usd_amount_col = RawDataAttribute.RAW_USD_AMOUNT.value
        raw_ils_amount_col = RawDataAttribute.RAW_ILS_AMOUNT.value
        commission_col = RawDataAttribute.COMMISSION_FEE.value
        add_fees_col = RawDataAttribute.ADDITIONAL_FEES.value

        for col in (date_col, action_col):
            if col not in df.columns:
                raise ValueError(f"Missing required column {col!r} in raw_df")

        # Numeric coercion
        for col in (
            raw_usd_amount_col,
            raw_ils_amount_col,
            commission_col,
            add_fees_col,
            quantity_col,
            execution_price_col,
            estimated_tax_col,
        ):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        df["raw_usd"] = df[raw_usd_amount_col].fillna(0.0) if raw_usd_amount_col in df.columns else 0.0
        df["raw_ils"] = df[raw_ils_amount_col].fillna(0.0) if raw_ils_amount_col in df.columns else 0.0

        # Fees are always in USD in IBI exports
        df["fees_usd"] = 0.0
        if commission_col in df.columns:
            df["fees_usd"] = df["fees_usd"] + df[commission_col].fillna(0.0)
        if add_fees_col in df.columns:
            df["fees_usd"] = df["fees_usd"] + df[add_fees_col].fillna(0.0)
        df["fees_usd"] = df["fees_usd"].abs()

        df[action_col] = df[action_col].astype("string")

        symbol_series = (
            df[symbol_col].astype("string").fillna("").str.strip()
            if symbol_col in df.columns
            else pd.Series("", index=df.index, dtype="string")
        )
        paper_name_series = (
            df[paper_name_col].astype("string").fillna("")
            if paper_name_col in df.columns
            else pd.Series("", index=df.index, dtype="string")
        )

        # Tax action overrides — IBI encodes these as ambiguous symbol + Hebrew paper_name
        futures_tax_mask = symbol_series == "9992985"
        tax_symbol_mask = symbol_series.isin(["9992983", "9993983"])
        tax_shield_reset_mask = tax_symbol_mask & paper_name_series.str.contains("איפוס מגן מס", na=False)
        tax_shield_mask = (
            tax_symbol_mask & paper_name_series.str.contains("מגן מס", na=False) & ~tax_shield_reset_mask
        )
        tax_payable_mask = tax_symbol_mask & paper_name_series.str.contains("מס לשלם", na=False)
        tax_payment_mask = tax_symbol_mask & paper_name_series.str.contains("מס ששולם", na=False)
        tax_credit_mask = tax_symbol_mask & paper_name_series.str.contains("זיכוי מס", na=False)

        df.loc[futures_tax_mask, action_col] = RawActionType.FUTURES_TAX.value
        df.loc[tax_shield_reset_mask, action_col] = RawActionType.TAX_SHIELD_RESET.value
        df.loc[tax_shield_mask, action_col] = RawActionType.TAX_SHIELD_ACCRUAL.value
        df.loc[tax_payable_mask, action_col] = RawActionType.TAX_PAYABLE.value
        df.loc[tax_payment_mask, action_col] = RawActionType.TAX_PAYMENT.value
        df.loc[tax_credit_mask, action_col] = RawActionType.TAX_CREDIT.value

        is_trade = df[action_col].isin(_BUY_SELL_ACTIONS)

        df["delta_usd"] = df["raw_usd"]
        # IBI raw_usd_amount is net cash effect including fees.
        # Add fees back for buy/sell so delta_usd represents gross transaction value.
        df.loc[is_trade, "delta_usd"] = df.loc[is_trade, "raw_usd"] + df.loc[is_trade, "fees_usd"]

        df["delta_ils"] = df["raw_ils"]

        # For account cash actions, route the movement to the currency-specific delta field
        currency_series = (
            df[currency_col].astype("string").fillna("")
            if currency_col in df.columns
            else pd.Series("", index=df.index, dtype="string")
        )
        currency_clean = (
            currency_series.str.strip()
            .str.replace(r"\s+", "", regex=True)
            .str.replace('"', "", regex=False)
            .str.replace("׳", "", regex=False)
            .str.replace("״", "", regex=False)
            .str.lower()
        )
        is_ils_currency = currency_clean.str.contains("₪", na=False, regex=False)
        is_usd_currency = currency_clean.str.contains("$", na=False, regex=False)

        currency_routed_cash_actions = {
            RawActionType.CASH_DEPOSIT.value,
            RawActionType.ACCOUNT_MAINTENANCE_FEE.value,
            RawActionType.OTHER_CASH.value,
        }
        routed_cash_mask = df[action_col].isin(currency_routed_cash_actions)
        routed_ils_mask = routed_cash_mask & is_ils_currency
        routed_usd_mask = routed_cash_mask & is_usd_currency

        df.loc[routed_ils_mask, "delta_ils"] = df.loc[routed_ils_mask, "raw_ils"]
        df.loc[routed_ils_mask, "delta_usd"] = 0.0
        df.loc[routed_usd_mask, "delta_usd"] = df.loc[routed_usd_mask, "raw_usd"]
        df.loc[routed_usd_mask, "delta_ils"] = 0.0

        conversion_mask = (df[action_col] == RawActionType.FX_CONVERSION.value) & (symbol_series == "99028")
        if quantity_col in df.columns:
            df.loc[conversion_mask, "delta_usd"] = df.loc[conversion_mask, quantity_col].fillna(0.0)

        # USD cash deposit: "הפקדה" with symbol 99028 — amount is in raw_usd, no ILS movement
        usd_deposit_mask = (df[action_col] == RawActionType.CASH_DEPOSIT.value) & (symbol_series == "99028")
        df.loc[usd_deposit_mask, "delta_usd"] = df.loc[usd_deposit_mask, "raw_usd"]
        df.loc[usd_deposit_mask, "delta_ils"] = 0.0

        out = pd.DataFrame(
            {
                "date": pd.to_datetime(df[date_col], errors="coerce"),
                "action_type": df[action_col],
                "symbol": df[symbol_col] if symbol_col in df.columns else None,
                "paper_name": df[paper_name_col].fillna("").astype("string") if paper_name_col in df.columns else "",
                "quantity": df[quantity_col].fillna(0.0) if quantity_col in df.columns else 0.0,
                "execution_price": df[execution_price_col].fillna(0.0) if execution_price_col in df.columns else 0.0,
                "delta_usd": df["delta_usd"],
                "delta_ils": df["delta_ils"],
                "fees_usd": df["fees_usd"],
                "estimated_capital_gains_tax": (
                    df[estimated_tax_col].fillna(0.0) if estimated_tax_col in df.columns else 0.0
                ),
                "expected_ils_balance": (
                    df[ils_balance_col] if ils_balance_col in df.columns else pd.Series(pd.NA, index=df.index)
                ),
            }
        )

        # Pass through optional source-order metadata for stable same-day sorting
        if "_source_order" in df.columns:
            out["_source_order"] = pd.to_numeric(df["_source_order"], errors="coerce").fillna(0.0)
        if "_date_desc" in df.columns:
            out["_date_desc"] = df["_date_desc"].fillna(False).astype(bool)

        for col in ("quantity", "execution_price", "estimated_capital_gains_tax", "delta_usd", "delta_ils", "fees_usd"):
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0)

        out["expected_ils_balance"] = pd.to_numeric(out["expected_ils_balance"], errors="coerce")

        out.sort_values(by="date", inplace=True, kind="mergesort", na_position="last")
        out.reset_index(drop=True, inplace=True)
        return out


__all__ = [
    "RawDataAttribute",
    "RawActionType",
    "HEBREW_COLUMNS_MAP",
    "HEBREW_ACTION_TYPE_MAP",
    "load_single",
    "IBILoader",
]