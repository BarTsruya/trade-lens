from __future__ import annotations

import io
from abc import ABC, abstractmethod
from typing import Union

import pandas as pd


class BrokerLoader(ABC):
    """Abstract base class for broker-specific file loaders and normalizers.

    To add a new broker:
    1. Create ``trade_lens/brokers/<broker_name>.py``
    2. Subclass ``BrokerLoader`` and implement ``load_raw`` and ``normalize``
    3. Register the class in ``trade_lens/brokers/registry.py``
    """

    broker_id: str

    @abstractmethod
    def load_raw(self, source: Union[str, bytes, io.IOBase]) -> pd.DataFrame:
        """Load a broker export file and return a raw DataFrame.

        The returned DataFrame must use ``RawDataAttribute`` column names and
        have ``action_type`` values already mapped to ``RawActionType`` enum
        string values.
        """

    @abstractmethod
    def normalize(self, raw_df: pd.DataFrame) -> pd.DataFrame:
        """Transform a raw DataFrame (from ``load_raw``) into the canonical ledger schema.

        Required output columns:
            date, action_type, symbol, paper_name, quantity, execution_price,
            delta_usd, delta_ils, fees_usd, estimated_capital_gains_tax,
            expected_ils_balance

        Optional pass-through metadata columns (preserved when present in raw_df):
            _source_order, _date_desc
        """


__all__ = ["BrokerLoader"]
