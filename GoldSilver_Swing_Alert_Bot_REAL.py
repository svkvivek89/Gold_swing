
import os
import yfinance as yf
import pandas as pd
import ta
import requests
from datetime import datetime

# === Telegram Credentials ===
# Read from environment variables only. A bot token was previously hardcoded
# here and committed to git history — rotate it via BotFather and set
# TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID in your environment before running.
telegram_bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
telegram_chat_id = os.environ["TELEGRAM_CHAT_ID"]

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage"
    payload = {"chat_id": telegram_chat_id, "text": message}
    try:
        response = requests.post(url, data=payload)
        if not response.ok:
            print(f"Telegram API rejected the message ({response.status_code}): {response.text}")
    except Exception as e:
        print(f"Failed to send message: {e}")

ATR_WINDOW = 14
BB_WINDOW = 20
BB_STD = 2
STOP_ATR_MULT = 2.0
TARGET_ATR_MULT = 1.0
MAX_HOLD_DAYS = 7

# Selected via strategy_search.py's grid search over 730 days of 1h bars:
# buy when price closes below the lower Bollinger Band, exit at 1x ATR14
# profit or 2x ATR14 loss (whichever comes first), or after MAX_HOLD_DAYS.
# Backtested: 69.8% win rate, 6.4 trades/week, profit factor 1.18 (combined
# across GC=F/SI=F). The edge is thin in absolute terms (well under 0.1%
# average return per trade) — real spread/slippage could erode it.
def fetch_and_analyze(symbol):
    try:
        data = yf.download(symbol, interval='1h', period='60d')
        if data.empty:
            return

        # yfinance returns MultiIndex columns (Price, Ticker) even for a
        # single-symbol download; flatten so data['Close'] is a plain Series.
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        data['ATR'] = ta.volatility.AverageTrueRange(
            data['High'], data['Low'], data['Close'], window=ATR_WINDOW
        ).average_true_range()
        bb = ta.volatility.BollingerBands(data['Close'], window=BB_WINDOW, window_dev=BB_STD)
        data['BB_low'] = bb.bollinger_lband()

        last = data.iloc[-1]
        prev = data.iloc[-2]

        signal = None

        if last['Close'] < last['BB_low'] and prev['Close'] >= prev['BB_low']:
            entry = last['Close']
            atr = last['ATR']
            stop = entry - STOP_ATR_MULT * atr
            target = entry + TARGET_ATR_MULT * atr
            signal = (
                f"📈 BUY Signal on {symbol}\n"
                f"Entry: {entry:.2f}\n"
                f"Stop: {stop:.2f}\n"
                f"Target: {target:.2f}\n"
                f"Max hold: {MAX_HOLD_DAYS} days\n"
                f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )

        if signal:
            send_telegram_message(signal)
        else:
            print(f"No signal for {symbol} at {datetime.now()}")

    except Exception as e:
        print(f"Error for {symbol}: {e}")

# === Symbols to Track ===
# 'XAUUSD=X' / 'XAGUSD=X' are not valid Yahoo Finance tickers (404 "Quote not
# found"). Use the COMEX futures symbols instead, which Yahoo does serve.
symbols = ['GC=F', 'SI=F']  # Gold and Silver futures

if __name__ == "__main__":
    for symbol in symbols:
        fetch_and_analyze(symbol)
