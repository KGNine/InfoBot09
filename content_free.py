import os
import re
import html
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

LAT, LON = -31.77, -52.34  # Pelotas/RS

PILARES = [
    {"nome": "🪙 Cripto Pulse", "tipo": "rss", "rss": "https://www.coindesk.com/arc/outboundfeeds/rss/", "idioma": "en"},
    {"nome": "🇧🇷 Termômetro BR", "tipo": "rss", "rss": "https://g1.globo.com/rss/g1/economia/", "idioma": "pt"},
    {"nome": "🌍 Giro Global", "tipo": "rss", "rss": "http://feeds.bbci.co.uk/news/business/rss.xml", "idioma": "en"},
    {"nome": "📈 Sala de Trade", "tipo": "rss", "rss": "https://www.investing.com/rss/news.rss", "idioma": "en"},
    {"nome": "🤖 Radar IA", "tipo": "rss", "rss": "https://techcrunch.com/category/artificial-intelligence/feed/", "idioma": "en"},
    {"nome": "🌦️ Clima & Mercado", "tipo": "clima", "idioma": "pt"},
]

HORARIOS_UTC = {10: 0, 12: 1, 14: 2, 16: 3, 18: 4, 20: 5}


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


def limpar_html(texto):
    texto = re.sub(r"<[^>]+>", " ", texto or "")
    texto = html.unescape(texto)
    return re.sub(r"\s+", " ", texto).strip()


def extrair_imagem(item):
    enc = item.find("enclosure")
    if enc is not None:
        url = enc.attrib.get("url", "")
        tipo = enc.attrib.get("type", "")
        if url and (tipo.startswith("image") or url.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))):
            return url
    for el in item.iter():
        tag = el.tag.split("}")[-1]
        if tag in ("content", "thumbnail") and el.attrib.get("url"):
            return el.attrib["url"]
    desc = item.findtext("description", default="") or ""
    m = re.search(r'<img[^>]+src=["\']([^"\']+)', desc)
    return m.group(1) if m else None


def buscar_manchete(url, idioma):
    resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    item = root.find(".//item")
    if item is None:
        return None

    titulo = (item.findtext("title", default="") or "").strip()
    descricao = limpar_html(item.findtext("description", default=""))[:400]
    imagem = extrair_imagem(item)

    return {
        "titulo": traduzir(titulo, idioma),
        "descricao": traduzir(descricao, idioma)[:300] if descricao else "",
        "imagem": imagem,
    }


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
    imagem = None

    try:
        if pilar["tipo"] == "rss":
            info = buscar_manchete(pilar["rss"], pilar["idioma"])
            if info:
                corpo = f"*{info['titulo']}*"
                if info["descricao"]:
                    corpo += f"\n\n{info['descricao']}"
                imagem = info["imagem"]
            else:
                corpo = "sem novidades no momento"
        elif pilar["tipo"] == "clima":
            corpo = buscar_clima()
        else:
            corpo = "conteúdo indisponível"
    except Exception as e:
        corpo = f"fonte indisponível ({type(e).__name__})"

    texto = f"*{pilar['nome']}* — {agora}\n\n{corpo}"
    return texto, imagem


def enviar_texto(texto):
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": texto, "parse_mode": "Markdown"}
    resp = requests.post(f"{BASE_URL}/sendMessage", data=payload, timeout=15)
    resp.raise_for_status()


def enviar_foto(imagem_url, legenda):
    if len(legenda) > 1024:
        legenda = legenda[:1000] + "…"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "photo": imagem_url, "caption": legenda, "parse_mode": "Markdown"}
    resp = requests.post(f"{BASE_URL}/sendPhoto", data=payload, timeout=20)
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

    texto, imagem = montar_mensagem(indice)

    try:
        if imagem:
            enviar_foto(imagem, texto)
        else:
            enviar_texto(texto)
    except Exception as e:
        print("Falha ao enviar com imagem, tentando só texto:", e)
        enviar_texto(texto)

    print("Mensagem enviada com sucesso:")
    print(texto)


if __name__ == "__main__":
    main()
