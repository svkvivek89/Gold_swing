import numpy as np
import pandas as pd
import ta
import yfinance as yf

SYMBOLS = ['GC=F', 'SI=F']
MAX_HOLD_HOURS = 168  # 1 week of 1h bars, per the user's max holding period
ATR_STOP_MULT = 1.5
ATR_TARGET_MULT = 3.0  # 2:1 reward:risk


def load(symbol):
    data = yf.download(symbol, interval='1h', period='730d')
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    data['EMA20'] = ta.trend.ema_indicator(data['Close'], window=20)
    data['EMA50'] = ta.trend.ema_indicator(data['Close'], window=50)
    data['EMA200'] = ta.trend.ema_indicator(data['Close'], window=200)
    data['RSI'] = ta.momentum.RSIIndicator(data['Close'], window=14).rsi()
    data['ATR'] = ta.volatility.AverageTrueRange(
        data['High'], data['Low'], data['Close'], window=14
    ).average_true_range()
    return data


def simulate(data, entry_mask, direction, label, stop_mult=ATR_STOP_MULT, target_mult=ATR_TARGET_MULT):
    """Walk each signal forward bar-by-bar with a real ATR stop and a
    hard MAX_HOLD_HOURS timeout, using High/Low (not just Close) to decide
    which was hit first. target_mult=None means no fixed target — ride the
    trade to the stop or the 1-week timeout, whichever comes first."""
    trades = []
    for i in np.where(entry_mask.values)[0]:
        if i + 1 >= len(data):
            continue
        entry = data['Close'].iloc[i]
        atr = data['ATR'].iloc[i]
        if pd.isna(atr) or atr == 0:
            continue

        target = None
        if direction == 1:
            stop = entry - stop_mult * atr
            if target_mult is not None:
                target = entry + target_mult * atr
        else:
            stop = entry + stop_mult * atr
            if target_mult is not None:
                target = entry - target_mult * atr

        exit_price, exit_type, hold = None, 'timeout', 0
        last_j = min(i + MAX_HOLD_HOURS, len(data) - 1)
        for j in range(i + 1, last_j + 1):
            hi, lo = data['High'].iloc[j], data['Low'].iloc[j]
            hold = j - i
            if direction == 1:
                if lo <= stop:
                    exit_price, exit_type = stop, 'stop'
                    break
                if target is not None and hi >= target:
                    exit_price, exit_type = target, 'target'
                    break
            else:
                if hi >= stop:
                    exit_price, exit_type = stop, 'stop'
                    break
                if target is not None and lo <= target:
                    exit_price, exit_type = target, 'target'
                    break
        if exit_price is None:
            exit_price, hold = data['Close'].iloc[last_j], last_j - i

        ret_pct = direction * (exit_price / entry - 1) * 100
        trades.append({'ret_pct': ret_pct, 'exit_type': exit_type, 'hold_h': hold})

    df = pd.DataFrame(trades)
    if df.empty:
        print(f"    {label}: no trades")
        return
    win_rate = (df['ret_pct'] > 0).mean() * 100
    wins = df.loc[df['ret_pct'] > 0, 'ret_pct'].sum()
    losses = -df.loc[df['ret_pct'] <= 0, 'ret_pct'].sum()
    pf = wins / losses if losses > 0 else float('inf')
    print(
        f"    {label}: n={len(df)}  win_rate={win_rate:.0f}%  "
        f"avg={df['ret_pct'].mean():+.2f}%  profit_factor={pf:.2f}  "
        f"avg_hold={df['hold_h'].mean():.0f}h  exits={df['exit_type'].value_counts().to_dict()}"
    )


def run(symbol):
    data = load(symbol)
    prev_rsi = data['RSI'].shift(1)

    # Baseline: the current live bot logic (RSI crossing 50 as trigger).
    base_buy = (
        (data['Close'] > data['EMA200']) & (data['Close'] < data['EMA20'])
        & (prev_rsi < 50) & (data['RSI'] > 50) & (data['Close'] > data['Open'])
    )
    base_sell = (
        (data['Close'] < data['EMA200']) & (data['Close'] > data['EMA20'])
        & (prev_rsi > 50) & (data['RSI'] < 50) & (data['Close'] < data['Open'])
    )

    # Candidate: require a real oversold/overbought dip in the last 10 bars
    # before the RSI-50 reclaim (filters noise), and a stronger downtrend
    # filter for shorts (EMA50 below EMA200, not just price below EMA200).
    rsi_min_10 = data['RSI'].rolling(10).min()
    rsi_max_10 = data['RSI'].rolling(10).max()
    cand_buy = (
        (data['Close'] > data['EMA200']) & (rsi_min_10 < 40)
        & (prev_rsi <= 50) & (data['RSI'] > 50)
    )
    cand_sell = (
        (data['Close'] < data['EMA200']) & (data['EMA50'] < data['EMA200'])
        & (rsi_max_10 > 60) & (prev_rsi >= 50) & (data['RSI'] < 50)
    )

    print(f"\n=== {symbol}: {len(data)} bars, {data.index[0].date()} to {data.index[-1].date()} ===")
    print(f"  Baseline (current live logic), ATR {ATR_STOP_MULT}x stop / {ATR_TARGET_MULT}x target, {MAX_HOLD_HOURS}h max hold:")
    simulate(data, base_buy, 1, 'BUY ')
    simulate(data, base_sell, -1, 'SELL')
    print(f"  Candidate (oversold-dip + reclaim, stronger short filter), same stop/target/timeout:")
    simulate(data, cand_buy, 1, 'BUY ')
    simulate(data, cand_sell, -1, 'SELL')
    print(f"  Candidate, wide stop (3x ATR), no fixed target — ride to stop or {MAX_HOLD_HOURS}h timeout:")
    simulate(data, cand_buy, 1, 'BUY ', stop_mult=3.0, target_mult=None)
    simulate(data, cand_sell, -1, 'SELL', stop_mult=3.0, target_mult=None)


if __name__ == "__main__":
    for sym in SYMBOLS:
        run(sym)
