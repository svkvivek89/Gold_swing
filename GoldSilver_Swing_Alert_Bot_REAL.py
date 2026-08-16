
import os
import yfinance as yf
import pandas as pd
import ta
import requests
from datetime import datetime

# === Telegram Credentials ===
# Prefer environment variables; fall back to the previous hardcoded values so
# existing setups keep working. Rotate the bot token (it was committed to git
# history) and set TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID going forward.
telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "7939331779:AAHbQL6qOzq6u3jn7QipxBlKwqo66SWduy0")
telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "6544776630")

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage"
    payload = {"chat_id": telegram_chat_id, "text": message}
    try:
        requests.post(url, data=payload)
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
symbols = ['XAUUSD=X', 'XAGUSD=X']  # Yahoo Finance codes for Gold and Silver

# === Run the Check ===
for symbol in symbols:
    fetch_and_analyze(symbol)
