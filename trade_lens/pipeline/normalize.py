from __future__ import annotations

import pandas as pd

from trade_lens.brokers.ibi import RawActionType, RawDataAttribute

BUY_SELL_ACTIONS = {RawActionType.BUY.value, RawActionType.SELL.value}


def to_ledger(raw_df: pd.DataFrame) -> pd.DataFrame:
    """
    Canonical output columns:
      - date
      - action_type
            - symbol
            - paper_name
            - quantity
            - execution_price
            - delta_usd (signed)
            - delta_ils (signed)
            - fees_usd (>= 0, USD fees magnitude)
            - estimated_capital_gains_tax
    """
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

    # numeric coercion
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

    # Fees are ALWAYS in USD in your IBI export
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

    # Tax action overrides for ambiguous symbols.
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

    is_trade = df[action_col].isin(BUY_SELL_ACTIONS)

    df["delta_usd"] = df["raw_usd"]
    # IBI raw_usd_amount is net cash effect including fees.
    # Add fees back for buy/sell so delta_usd represents gross transaction value excluding fees.
    df.loc[is_trade, "delta_usd"] = df.loc[is_trade, "raw_usd"] + df.loc[is_trade, "fees_usd"]

    # Keep ILS cash movement as the raw shekel effect per row.
    df["delta_ils"] = df["raw_ils"]

    # For account cash actions, route the movement to the currency-specific delta field.
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
    is_ils_currency = currency_clean.str.contains(r"ils|nis|שח|שקל", na=False)
    is_usd_currency = currency_clean.str.contains(r"usd|\$|דולר", na=False)

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
            "estimated_capital_gains_tax": df[estimated_tax_col].fillna(0.0) if estimated_tax_col in df.columns else 0.0,
            "expected_ils_balance": (
                df[ils_balance_col] if ils_balance_col in df.columns else pd.Series(pd.NA, index=df.index)
            ),
        }
    )

    # Pass through optional source-order metadata used for stable same-day ordering.
    if "_source_order" in df.columns:
        out["_source_order"] = pd.to_numeric(df["_source_order"], errors="coerce").fillna(0.0)
    if "_date_desc" in df.columns:
        out["_date_desc"] = df["_date_desc"].fillna(False).astype(bool)

    for col in (
        "quantity",
        "execution_price",
        "estimated_capital_gains_tax",
        "delta_usd",
        "delta_ils",
        "fees_usd",
    ):
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0)

    out["expected_ils_balance"] = pd.to_numeric(out["expected_ils_balance"], errors="coerce")

    out.sort_values(by="date", inplace=True, kind="mergesort", na_position="last")
    out.reset_index(drop=True, inplace=True)
    return out


__all__ = ["to_ledger"]