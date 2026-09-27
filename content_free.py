import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

LAT, LON = -31.77, -52.34  # Pelotas/RS

PILARES = [
    {"nome": "🪙 Cripto Pulse", "tipo": "rss", "rss": "https://www.coindesk.com/arc/outboundfeeds/rss/", "idioma": "en"},
    {"nome": "🇧🇷 Termômetro BR", "tipo": "rss", "rss": "https://g1.globo.com/rss/g1/economia/", "idioma": "pt"},
    {"nome": "🌍 Giro Global", "tipo": "rss", "rss": "http://feeds.bbci.co.uk/news/business/rss.xml", "idioma": "en"},
    {"nome": "📈 Sala de Trade", "tipo": "rss", "rss": "https://www.investing.com/rss/news.rss", "idioma": "en"},
    {"nome": "🤖 Radar IA", "tipo": "rss", "rss": "https://techcrunch.com/category/artificial-intelligence/feed/", "idioma": "en"},
    {"nome": "🌦️ Clima & Mercado", "tipo": "clima", "idioma": "pt"},
]

# Hora em UTC -> indice do pilar em PILARES
HORARIOS_UTC = {10: 0, 12: 1, 14: 2, 16: 3, 18: 4, 20: 5}

CAMPANHAS_VIP = [
    "Isso é só a manchete. No VIP, a gente te diz o que fazer com essa informação — antes que o mercado já tenha precificado.",
    "Quem está no grupo VIP já recebeu a leitura completa disso, com o ativo mais afetado apontado. Você quer continuar sabendo por último?",
    "O que essa notícia muda pra quem investe? A resposta fica no VIP — aqui é o dado, lá é a decisão.",
]


def traduzir(texto, idioma_origem):
    if idioma_origem == "pt" or not texto:
        return texto
    try:
        url = "https://api.mymemory.translated.net/get"
        params = {"q": texto[:480], "langpair": f"{idioma_origem}|pt-BR"}
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        traduzido = resp.json()["responseData"]["translatedText"]
        return traduzido or texto
    except Exception:
        return texto


def buscar_manchete(url, idioma):
    resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    item = root.find(".//item")
    if item is None:
        return None
    titulo = (item.findtext("title", default="") or "").strip()
    return traduzir(titulo, idioma)


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

    tmax = daily["temperature_2m_max"][0]
    tmin = daily["temperature_2m_min"][0]
    chuva_hoje = daily["precipitation_sum"][0]
    total_chuva = sum(daily["precipitation_sum"][:3])

    texto = f"Hoje: {tmin:.0f}°C a {tmax:.0f}°C, chuva prevista {chuva_hoje:.0f}mm."
    if total_chuva < 2:
        texto += " ⚠️ Pouquíssima chuva nos próximos dias — atenção a lavouras da região."
    elif total_chuva > 60:
        texto += " ⚠️ Volume alto de chuva previsto — risco de excesso hídrico agrícola."
    return texto


def montar_mensagem(indice_pilar):
    pilar = PILARES[indice_pilar]
    agora = datetime.now(timezone.utc).strftime("%d/%m %H:%M UTC")

    try:
        if pilar["tipo"] == "rss":
            conteudo = buscar_manchete(pilar["rss"], pilar["idioma"]) or "sem novidades no momento"
        elif pilar["tipo"] == "clima":
            conteudo = buscar_clima()
        else:
            conteudo = "conteúdo indisponível"
    except Exception as e:
        conteudo = f"fonte indisponível ({type(e).__name__})"

    campanha = CAMPANHAS_VIP[indice_pilar % len(CAMPANHAS_VIP)]

    return f"*{pilar['nome']}* — {agora}\n\n{conteudo}\n\n🔓 _{campanha}_"


def enviar_telegram(texto):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": texto, "parse_mode": "Markdown"}
    resp = requests.post(url, data=payload, timeout=15)
    resp.raise_for_status()


def main():
    forcar = os.environ.get("FORCAR_PILAR", "").strip()
    if forcar.isdigit() and int(forcar) < len(PILARES):
        indice = int(forcar)
    else:
        indice = HORARIOS_UTC.get(datetime.now(timezone.utc).hour)

    if indice is None:
        print("Hora atual fora do roteiro — nada a enviar.")
        return

    mensagem = montar_mensagem(indice)
    enviar_telegram(mensagem)
    print("Mensagem enviada com sucesso:")
    print(mensagem)


if __name__ == "__main__":
    main()
