from GoldSilver_Swing_Alert_Bot_REAL import fetch_and_analyze

# Run once for both symbols
for symbol in ['XAUUSD=X', 'XAGUSD=X']:
    fetch_and_analyze(symbol)
