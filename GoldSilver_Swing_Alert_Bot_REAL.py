
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

def fetch_and_analyze(symbol):
    try:
        # '2h' is not a valid yfinance/Yahoo interval (valid: 1m,2m,5m,15m,30m,
        # 60m,90m,1h,1d,5d,1wk,1mo,3mo), and 15d of data isn't enough history
        # to compute a 200-period EMA. Use '1h' bars over 60d instead.
        data = yf.download(symbol, interval='1h', period='60d')
        if data.empty:
            return

        # yfinance returns MultiIndex columns (Price, Ticker) even for a
        # single-symbol download; flatten so data['Close'] is a plain Series.
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        data['EMA20'] = ta.trend.ema_indicator(data['Close'], window=20)
        data['EMA200'] = ta.trend.ema_indicator(data['Close'], window=200)
        data['RSI'] = ta.momentum.RSIIndicator(data['Close'], window=14).rsi()

        last = data.iloc[-1]
        prev = data.iloc[-2]

        signal = None

        if last['Close'] > last['EMA200'] and last['Close'] < last['EMA20'] and prev['RSI'] < 50 and last['RSI'] > 50 and last['Close'] > last['Open']:
            signal = f"📈 BUY Signal on {symbol}\nPrice: {last['Close']:.2f}\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M')}"

        elif last['Close'] < last['EMA200'] and last['Close'] > last['EMA20'] and prev['RSI'] > 50 and last['RSI'] < 50 and last['Close'] < last['Open']:
            signal = f"📉 SELL Signal on {symbol}\nPrice: {last['Close']:.2f}\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M')}"

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
