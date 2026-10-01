import os
import re
import requests
from datetime import datetime, timezone
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

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


def achar_destaque(data):
    melhor_id, melhor_var = None, -1
    for coin_id in COINS:
        info = data.get(coin_id)
        if not info:
            continue
        var = abs(info.get("usd_24h_change", 0) or 0)
        if var > melhor_var:
            melhor_var, melhor_id = var, coin_id
    return melhor_id


def gerar_imagem_destaque(coin_id, data):
    label = COINS[coin_id]
    simbolo = re.search(r"\(([A-Z]+)\)", label)
    simbolo = simbolo.group(1) if simbolo else label[:4].upper()
    nome = label.split(" (")[0]
    info = data[coin_id]
    preco = info["usd"]
    variacao = info.get("usd_24h_change", 0) or 0
    positivo = variacao >= 0

    cor_fundo = "#0a3d2e" if positivo else "#3d0a0a"
    cor_destaque = "#2ecc71" if positivo else "#e74c3c"
    seta = "▲" if positivo else "▼"

    fig, ax = plt.subplots(figsize=(8, 8), dpi=100)
    fig.patch.set_facecolor(cor_fundo)
    ax.set_facecolor(cor_fundo)
    ax.axis("off")
    ax.text(0.5, 0.68, simbolo, ha="center", va="center", fontsize=90, fontweight="bold", color="white")
    ax.text(0.5, 0.52, nome, ha="center", va="center", fontsize=26, color="#cccccc")
    ax.text(0.5, 0.34, f"${preco:,.2f}", ha="center", va="center", fontsize=44, color="white", fontweight="bold")
    ax.text(0.5, 0.18, f"{seta} {abs(variacao):.2f}% em 24h", ha="center", va="center",
            fontsize=32, color=cor_destaque, fontweight="bold")

    caminho = "/tmp/destaque.png"
    fig.savefig(caminho, facecolor=cor_fundo)
    plt.close(fig)
    return caminho


def enviar_texto(texto):
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": texto, "parse_mode": "Markdown"}
    resp = requests.post(f"{BASE_URL}/sendMessage", data=payload, timeout=15)
    resp.raise_for_status()


def enviar_foto_arquivo(caminho, legenda):
    with open(caminho, "rb") as f:
        payload = {"chat_id": TELEGRAM_CHAT_ID, "caption": legenda, "parse_mode": "Markdown"}
        resp = requests.post(f"{BASE_URL}/sendPhoto", data=payload, files={"photo": f}, timeout=30)
    resp.raise_for_status()


def main():
    data = get_prices()
    message = format_message(data)

    try:
        destaque_id = achar_destaque(data)
        caminho_img = gerar_imagem_destaque(destaque_id, data)
        enviar_foto_arquivo(caminho_img, message)
    except Exception as e:
        print("Falha ao gerar/enviar imagem, mandando só texto:", e)
        enviar_texto(message)

    print("Mensagem enviada com sucesso:")
    print(message)


if __name__ == "__main__":
    main()
