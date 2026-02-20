import yfinance as yf
import asyncio
import pandas as pd
from datetime import datetime
from typing import Dict, Optional

class MarketDataProvider:
    def __init__(self, tickers: list[str]):
        self.tickers = tickers
        self.data_cache: Dict[str, float] = {}

    async def fetch_price(self, ticker: str) -> Optional[float]:
        """
        מושך את המחיר האחרון של מניה ספציפית בצורה א-סינכרונית.
        """
        try:
            # אנחנו מריצים את yfinance ב-Thread נפרד כי היא ספרייה סינכרונית במקור
            loop = asyncio.get_event_loop()
            ticker_obj = yf.Ticker(ticker)
            
            # משיכת מחיר ה-Close האחרון
            data = await loop.run_in_executor(None, lambda: ticker_obj.fast_info)
            price = data['last_price']
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {ticker}: ${price:.2f}")
            return price
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")
            return None

    async def stream_market_data(self, interval_seconds: int = 5):
        """
        סימולציה של Stream - מושך נתונים כל X שניות.
        """
        print(f"Starting market data stream for: {self.tickers}")
        while True:
            tasks = [self.fetch_price(ticker) for ticker in self.tickers]
            prices = await asyncio.gather(*tasks)
            
            # עדכון ה-Cache (כאן בהמשך יבוא החיבור ל-Database)
            for ticker, price in zip(self.tickers, prices):
                if price:
                    self.data_cache[ticker] = price
            
            await asyncio.sleep(interval_seconds)

# נקודת כניסה להרצה
if __name__ == "__main__":
    # נגדיר את המניות שאנחנו רוצים לעקוב אחריהן
    watch_list = ["AAPL", "NVDA", "TSLA", "MSFT"]
    provider = MarketDataProvider(watch_list)
    
    try:
        asyncio.run(provider.stream_market_data(interval_seconds=5))
    except KeyboardInterrupt:
        print("\nStream stopped by user.")