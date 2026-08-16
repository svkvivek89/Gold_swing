from datetime import datetime

from GoldSilver_Swing_Alert_Bot_REAL import send_telegram_message

send_telegram_message(
    f"✅ Test message from Gold Silver Swing Alert Bot\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
)
print("Test message sent (check the chat, and the response above for delivery errors).")
