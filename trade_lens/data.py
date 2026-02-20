import pandas as pd
import sys

HEBREW_TO_ENGLISH_COLUMNS = {
    "תאריך": 'action_date',
    "סוג פעולה": 'action_type',
    "שם נייר": 'paper_name',
    "מס' נייר / סימבול": 'paper_symbol',
    "כמות": 'quantity',
    "שער ביצוע": 'execution_price',
    "מטבע": 'currency',
    "עמלת פעולה": 'commission_fee',
    "עמלות נלוות": 'additional_fees',
    'תמורה במט"ח': 'total_value_foreign',
    "תמורה בשקלים": 'total_value_shekel',
    "יתרה שקלית": 'shekel_balance',
    "אומדן מס רווחי הון": 'estimated_capital_gains_tax',
}


class RawExcelData:
    """
    Represents the contents of an Excel file that contains the TradeLens
    export.  The spreadsheet is read “as‑is” and then the Hebrew column
    names are mapped to English using the global dictionary above.
    """

    def __init__(self, path: str) -> None:
        self.path = path
        self.df: pd.DataFrame | None = None

    def load(self) -> pd.DataFrame:
        """Read the workbook into `self.df` without altering the column names.

        Raises
        ------
        FileNotFoundError
            if the file cannot be found on disk.
        RuntimeError
            for any other error encountered while using pandas to read the
            workbook.
        """
        try:
            self.df = pd.read_excel(self.path)
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"Excel file not found: {self.path}") from exc
        except Exception as exc:  # pandas raises a variety of subclasses
            raise RuntimeError(f"Failed to load Excel file {self.path}: {exc}") from exc

        return self.df

    def rename_columns(self) -> pd.DataFrame:
        """
        Rename the columns in `self.df` according to the translation table.
        If the frame has not yet been loaded it will call `load()` first.

        Raises
        ------
        RuntimeError
            if pandas fails to perform the rename for some reason.
        """
        if self.df is None:
            self.load()

        try:
            self.df = self.df.rename(columns=HEBREW_TO_ENGLISH_COLUMNS)
        except Exception as exc:
            raise RuntimeError(f"Column rename failed: {exc}") from exc

        return self.df

    def load_and_rename(self) -> pd.DataFrame:
        """Convenience: load the file and then rename the columns."""
        return self.rename_columns()


def _main() -> None:
    """Simple command‑line driver for manual testing."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Load a TradeLens Excel file and rename its columns."
    )
    parser.add_argument("path", help="path to the Excel workbook")
    args = parser.parse_args()

    loader = RawExcelData(args.path)
    try:
        df = loader.load_and_rename()
    except Exception as exc:  # propagate a readable error code
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(df.columns)


if __name__ == "__main__":
    _main()

