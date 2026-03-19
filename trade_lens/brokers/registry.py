from __future__ import annotations

from trade_lens.brokers.base import BrokerLoader
from trade_lens.brokers.ibi import IBILoader

# Maps broker_id strings to their loader classes.
# To add a new broker: import its loader class and add an entry here.
BROKERS: dict[str, type[BrokerLoader]] = {
    "ibi": IBILoader,
}


def get_broker(broker_id: str) -> BrokerLoader:
    """Return an instantiated BrokerLoader for the given broker_id.

    Raises KeyError if the broker is not registered.
    """
    try:
        return BROKERS[broker_id]()
    except KeyError:
        available = ", ".join(sorted(BROKERS))
        raise KeyError(f"Unknown broker {broker_id!r}. Available: {available}") from None


__all__ = ["BROKERS", "get_broker"]
