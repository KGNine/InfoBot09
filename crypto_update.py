import os
import requests
from datetime import datetime, timezone

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

COINS = {
    "bitcoin": "Bitcoin (BTC)",
    "ethereum": "Ethereum (ETH)",
    "binancecoin": "BNB",
    "solana": "Solana (SOL)",
    "ripple": "XRP",
}


def get_prices():
    ids = ",".join(COINS.keys())
    url = (
        "https://api.coingecko.com/api/v3/simple/price"
        f"?ids={ids}&vs_currencies=usd,brl&include_24hr_change=true"
    )
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return resp.json()


def format_message(data):
    now = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    lines = [f"*Atualização de criptomoedas* — {now}", ""]

    for coin_id, label in COINS.items():
        info = data.get(coin_id)
        if not info:
            continue
        usd = info.get("usd")
        brl = info.get("brl")
        change = info.get("usd_24h_change", 0) or 0
        arrow = "🟢" if change >= 0 else "🔴"
        lines.append(
            f"{arrow} *{label}*: ${usd:,.2f} | R$ {brl:,.2f} ({change:+.2f}% em 24h)"
        )

    return "\n".join(lines)


def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
    }
    resp = requests.post(url, data=payload, timeout=15)
    resp.raise_for_status()


def main():
    data = get_prices()
    message = format_message(data)
    send_telegram_message(message)
    print("Mensagem enviada com sucesso:")
    print(message)


if __name__ == "__main__":
    main()
