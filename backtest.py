import pandas as pd
import ta
import yfinance as yf

# Keep these conditions identical to fetch_and_analyze() in
# GoldSilver_Swing_Alert_Bot_REAL.py — this measures how that exact logic
# would have performed historically.
SYMBOLS = ['GC=F', 'SI=F']
FORWARD_HORIZONS_HOURS = [24, 72, 168]  # ~1 day, ~3 days, ~1 week of 1h bars


def load(symbol):
    data = yf.download(symbol, interval='1h', period='730d')
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    data['EMA20'] = ta.trend.ema_indicator(data['Close'], window=20)
    data['EMA200'] = ta.trend.ema_indicator(data['Close'], window=200)
    data['RSI'] = ta.momentum.RSIIndicator(data['Close'], window=14).rsi()
    return data


def backtest(symbol):
    data = load(symbol)
    prev_rsi = data['RSI'].shift(1)

    buy = (
        (data['Close'] > data['EMA200'])
        & (data['Close'] < data['EMA20'])
        & (prev_rsi < 50) & (data['RSI'] > 50)
        & (data['Close'] > data['Open'])
    )
    sell = (
        (data['Close'] < data['EMA200'])
        & (data['Close'] > data['EMA20'])
        & (prev_rsi > 50) & (data['RSI'] < 50)
        & (data['Close'] < data['Open'])
    )

    print(f"\n=== {symbol}: {len(data)} bars, {data.index[0].date()} to {data.index[-1].date()} ===")
    print(f"BUY signals: {int(buy.sum())}   SELL signals: {int(sell.sum())}")

    for name, mask, direction in [('BUY', buy, 1), ('SELL', sell, -1)]:
        idxs = data.index[mask]
        if len(idxs) == 0:
            print(f"\n{name}: no signals")
            continue

        rows = []
        for ts in idxs:
            i = data.index.get_loc(ts)
            entry = data['Close'].iloc[i]
            row = {'time': ts}
            for h in FORWARD_HORIZONS_HOURS:
                if i + h < len(data):
                    fut = data['Close'].iloc[i + h]
                    row[f'{h}h_ret_pct'] = direction * (fut / entry - 1) * 100
            rows.append(row)
        df = pd.DataFrame(rows)

        print(f"\n{name} signals ({len(df)}):")
        for h in FORWARD_HORIZONS_HOURS:
            col = f'{h}h_ret_pct'
            if col in df:
                valid = df[col].dropna()
                if len(valid):
                    win_rate = (valid > 0).mean() * 100
                    print(f"  +{h}h: avg {valid.mean():+.2f}%  win rate {win_rate:.0f}%  (n={len(valid)})")


for sym in SYMBOLS:
    backtest(sym)
