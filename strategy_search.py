import numpy as np
import pandas as pd
import ta
import yfinance as yf

SYMBOLS = ['GC=F', 'SI=F']
MAX_HOLD_HOURS = 168  # 1 week of 1h bars, per the user's max holding period
MIN_WIN_RATE = 60.0
MIN_TRADES_PER_WEEK = 5.0

# (target_mult, stop_mult) in units of ATR14. Skewed toward small targets /
# wider stops, since a high win rate needs the target to be easy to reach.
TARGET_STOP_GRID = [
    (0.5, 1.0), (0.5, 1.5), (0.5, 2.0),
    (0.75, 1.0), (0.75, 1.5), (0.75, 2.0),
    (1.0, 1.0), (1.0, 1.5), (1.0, 2.0),
]


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
    bb = ta.volatility.BollingerBands(data['Close'], window=20, window_dev=2)
    data['BB_low'] = bb.bollinger_lband()
    data['BB_high'] = bb.bollinger_hband()
    return data


def entry_rules(data):
    prev_rsi = data['RSI'].shift(1)
    prev_close = data['Close'].shift(1)
    return {
        'rsi30_cross_long': (prev_rsi >= 30) & (data['RSI'] < 30),
        'rsi35_cross_long': (prev_rsi >= 35) & (data['RSI'] < 35),
        'rsi40_cross_long': (prev_rsi >= 40) & (data['RSI'] < 40),
        'bb_lower_touch_long': (data['Close'] < data['BB_low']) & (prev_close >= data['BB_low'].shift(1)),
        'pullback_uptrend_long': (data['Close'] > data['EMA200']) & (data['Close'] < data['EMA20'] - 0.5 * data['ATR']),
        'rsi65_cross_short': (prev_rsi <= 65) & (data['RSI'] > 65),
        'rsi70_cross_short': (prev_rsi <= 70) & (data['RSI'] > 70),
        'bb_upper_touch_short': (data['Close'] > data['BB_high']) & (prev_close <= data['BB_high'].shift(1)),
    }


def simulate(data, entry_mask, direction, stop_mult, target_mult, max_hold=MAX_HOLD_HOURS):
    trades = []
    for i in np.where(entry_mask.values)[0]:
        if i + 1 >= len(data):
            continue
        entry = data['Close'].iloc[i]
        atr = data['ATR'].iloc[i]
        if pd.isna(atr) or atr == 0:
            continue

        if direction == 1:
            stop, target = entry - stop_mult * atr, entry + target_mult * atr
        else:
            stop, target = entry + stop_mult * atr, entry - target_mult * atr

        exit_price, exit_type, hold = None, 'timeout', 0
        last_j = min(i + max_hold, len(data) - 1)
        for j in range(i + 1, last_j + 1):
            hi, lo = data['High'].iloc[j], data['Low'].iloc[j]
            hold = j - i
            if direction == 1:
                if lo <= stop:
                    exit_price, exit_type = stop, 'stop'
                    break
                if hi >= target:
                    exit_price, exit_type = target, 'target'
                    break
            else:
                if hi >= stop:
                    exit_price, exit_type = stop, 'stop'
                    break
                if lo <= target:
                    exit_price, exit_type = target, 'target'
                    break
        if exit_price is None:
            exit_price, hold = data['Close'].iloc[last_j], last_j - i

        ret_pct = direction * (exit_price / entry - 1) * 100
        trades.append({'ret_pct': ret_pct, 'exit_type': exit_type, 'hold_h': hold})
    return pd.DataFrame(trades)


def evaluate_all():
    all_data = {sym: load(sym) for sym in SYMBOLS}
    span_days = max((d.index[-1] - d.index[0]).days for d in all_data.values())
    weeks = span_days / 7.0

    rule_names = list(entry_rules(all_data[SYMBOLS[0]]).keys())
    results = []
    for name in rule_names:
        direction = -1 if 'short' in name else 1
        for target_mult, stop_mult in TARGET_STOP_GRID:
            combined = []
            for sym in SYMBOLS:
                d = all_data[sym]
                mask = entry_rules(d)[name]
                combined.append(simulate(d, mask, direction, stop_mult, target_mult))
            all_df = pd.concat(combined, ignore_index=True) if combined else pd.DataFrame()
            if all_df.empty:
                continue
            n = len(all_df)
            win_rate = (all_df['ret_pct'] > 0).mean() * 100
            wins = all_df.loc[all_df['ret_pct'] > 0, 'ret_pct'].sum()
            losses = -all_df.loc[all_df['ret_pct'] <= 0, 'ret_pct'].sum()
            pf = wins / losses if losses > 0 else float('inf')
            results.append({
                'rule': name, 'target_mult': target_mult, 'stop_mult': stop_mult,
                'n': n, 'trades_per_week': n / weeks, 'win_rate': win_rate,
                'avg_ret_pct': all_df['ret_pct'].mean(), 'profit_factor': pf,
                'avg_hold_h': all_df['hold_h'].mean(),
            })
    return pd.DataFrame(results), weeks


if __name__ == "__main__":
    res, weeks = evaluate_all()
    pd.set_option('display.width', 200)
    pd.set_option('display.max_rows', 200)

    print(f"Backtest span: ~{weeks:.1f} weeks, combined across {len(SYMBOLS)} symbols\n")
    print("=== All combinations, sorted by profit factor ===")
    print(res.sort_values('profit_factor', ascending=False).to_string(index=False))

    qualifying = res[(res['win_rate'] >= MIN_WIN_RATE) & (res['trades_per_week'] >= MIN_TRADES_PER_WEEK)]
    print(f"\n=== QUALIFYING: win_rate >= {MIN_WIN_RATE}% AND trades_per_week >= {MIN_TRADES_PER_WEEK} ===")
    if qualifying.empty:
        print("NONE QUALIFY")
    else:
        print(qualifying.sort_values('profit_factor', ascending=False).to_string(index=False))
        best = qualifying.sort_values('profit_factor', ascending=False).iloc[0]
        print("\n=== BEST QUALIFYING STRATEGY ===")
        print(best.to_string())
