from enum import Enum
import pandas as pd
import sys

class RawDataAttribute(Enum):
    ACTION_DATE = "action_date"
    ACTION_TYPE= "action_type"
    PAPER_NAME= "paper_name"
    PAPER_SYMBOL= "paper_symbol"
    QUANTITY= "quantity"
    EXECUTION_PRICE= "execution_price"
    CURRENCY = "currency"
    COMMISSION_FEE = "commission_fee"
    ADDITIONAL_FEES = "additional_fees"
    TOTAL_VALUE_FOREIGN = "total_value_foreign"
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
    PURCHASE_FOREIGN = "purchase_foreign"
    DEPOSIT = "deposit"
    SALE_FOREIGN = "sale_foreign"
    PURCHASE_SHEKEL = "purchase_shekel"
    TRANSFER_CASH_SHEKEL = "transfer_cash_shekel"
    CASH_HANDLING_FEE_SHEKEL = "cash_handling_fee_shekel"
    WITHDRAWAL = "withdrawal"
    WITHDRAWAL_INTEREST_FOREIGN = 'withdrawal_interest_foreign'
    OTHER_CASH_SHEKEL = "other_cash_shekel"
    

HEBREW_ACTION_TYPE_MAP = {
    "מכירה שח": RawActionType.SALE_SHEKEL.value,
    "משיכת מס חול מטח": RawActionType.WITHDRAWAL_TAX_FOREIGN.value,
    "הפקדה דיבידנד מטח": RawActionType.DEPOSIT_DIVIDEND_FOREIGN.value,
    "קניה חול מטח": RawActionType.PURCHASE_FOREIGN.value,
    "הפקדה": RawActionType.DEPOSIT.value,
    "מכירה חול מטח": RawActionType.SALE_FOREIGN.value,
    "קניה שח": RawActionType.PURCHASE_SHEKEL.value,
    "העברה מזומן בשח": RawActionType.TRANSFER_CASH_SHEKEL.value,
    "דמי טיפול מזומן בשח": RawActionType.CASH_HANDLING_FEE_SHEKEL.value,
    "משיכה": RawActionType.WITHDRAWAL.value,
    'משיכת ריבית מט"ח': RawActionType.WITHDRAWAL_INTEREST_FOREIGN.value,
    "שונות מזומן בשח": RawActionType.OTHER_CASH_SHEKEL.value
}


class RawDataLoader:

    def __init__(self, path: str) -> None:
        self.path = path
        self.df: pd.DataFrame | None = None

    def load(self) -> pd.DataFrame:
        try:
            self.df = pd.read_excel(self.path)
            self.df.rename(columns=HEBREW_COLUMNS_MAP,inplace=True)
            self.df["action_type"] = self.df["action_type"].map(HEBREW_ACTION_TYPE_MAP)
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"Excel file not found: {self.path}") from exc
        except Exception as exc:  # pandas raises a variety of subclasses
            raise RuntimeError(f"Failed to load Excel file {self.path}: {exc}") from exc

        return self.df




def _main() -> None:
    """Simple command‑line driver for manual testing."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Load a TradeLens Excel file and rename its columns."
    )
    parser.add_argument("path", help="path to the Excel workbook")
    args = parser.parse_args()

    loader = RawDataLoader(args.path)
    try:
        df = loader.load()
    except Exception as exc:  # propagate a readable error code
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(df["action_type"][0:5])  # print the first few rows for sanity check


if __name__ == "__main__":
    _main()

