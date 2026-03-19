from __future__ import annotations

import pandas as pd

from trade_lens.brokers.base import BrokerLoader
from trade_lens.brokers.ibi import IBILoader

_DEFAULT_BROKER = IBILoader()


def to_ledger(raw_df: pd.DataFrame, broker: BrokerLoader = _DEFAULT_BROKER) -> pd.DataFrame:
    """Transform a raw DataFrame into the canonical ledger schema.

    Delegates to ``broker.normalize()``.  Defaults to :class:`IBILoader` for
    backward compatibility with existing call sites that omit the broker.
    """
    return broker.normalize(raw_df)


__all__ = ["to_ledger"]
