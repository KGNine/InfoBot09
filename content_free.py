import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# Coordenadas de Pelotas/RS
LAT, LON = -31.77, -52.34

PILARES = [
    {"nome": "🪙 Cripto Pulse", "tipo": "rss", "rss": "https://www.coindesk.com/arc/outboundfeeds/rss/"},
    {"nome": "🇧🇷 Termômetro BR", "tipo": "rss", "rss": "https://g1.globo.com/rss/g1/economia/"},
    {"nome": "🌍 Giro Global", "tipo": "rss", "rss": "http://feeds.bbci.co.uk/news/business/rss.xml"},
    {"nome": "📈 Sala de Trade", "tipo": "rss", "rss": "https://www.investing.com/rss/news.rss"},
    {"nome": "🤖 Radar IA", "tipo": "rss", "rss": "https://techcrunch.com/category/artificial-intelligence/feed/"},
    {"nome": "📍 Aqui & Agora (Pelotas)", "tipo": "manual"},
    {"nome": "🌦️ Clima & Mercado", "tipo": "clima"},
]

MAX_POR_PILAR = 2


def buscar_manchetes(url, limite=MAX_POR_PILAR):
    resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    itens = root.findall(".//item")[:limite]
    return [i.findtext("title", default="").strip() for i in itens if i.findtext("title")]


def buscar_clima():
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={LAT}&longitude={LON}"
        "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
        "&timezone=America%2FSao_Paulo"
    )
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    daily = resp.json()["daily"]

    linhas = []
    for i, dia in enumerate(daily["time"][:3]):
        tmax = daily["temperature_2m_max"][i]
        tmin = daily["temperature_2m_min"][i]
        chuva = daily["precipitation_sum"][i]
        linhas.append(f"{dia}: {tmin:.0f}°C a {tmax:.0f}°C, chuva prevista {chuva:.0f}mm")

    total_chuva = sum(daily["precipitation_sum"][:3])
    alerta = None
    if total_chuva < 2:
        alerta = "⚠️ Pouquíssima chuva prevista — atenção a impacto em lavouras da região"
    elif total_chuva > 60:
        alerta = "⚠️ Volume alto de chuva previsto — risco de excesso hídrico em áreas agrícolas"

    return linhas, alerta


def montar_mensagem():
    agora = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    linhas = [f"*L.I.C.A. — Resumo do dia* — {agora}", ""]

    for pilar in PILARES:
        linhas.append(f"*{pilar['nome']}*")

        if pilar["tipo"] == "manual":
            linhas.append("_atualizado manualmente no grupo_")
            linhas.append("")
            continue

        try:
            if pilar["tipo"] == "rss":
                manchetes = buscar_manchetes(pilar["rss"])
                if manchetes:
                    for m in manchetes:
                        linhas.append(f"• {m}")
                else:
                    linhas.append("_sem novidades no momento_")

            elif pilar["tipo"] == "clima":
                previsao, alerta = buscar_clima()
                for p in previsao:
                    linhas.append(f"• {p}")
                if alerta:
                    linhas.append(alerta)

        except Exception as e:
            linhas.append(f"_fonte indisponível ({type(e).__name__})_")

        linhas.append("")

    return "\n".join(linhas)


def enviar_telegram(texto):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": texto, "parse_mode": "Markdown"}
    resp = requests.post(url, data=payload, timeout=15)
    resp.raise_for_status()


def main():
    mensagem = montar_mensagem()
    enviar_telegram(mensagem)
    print("Mensagem enviada com sucesso:")
    print(mensagem)


if __name__ == "__main__":
    main()
