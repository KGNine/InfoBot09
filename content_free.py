#!/usr/bin/env python3
"""
L.I.C.A. | Conteúdo gratuito (6 pilares, 1 por horário) + texto completo para o VIP
Mudanças desta versão:
- "Também em pauta" removido de todos os pilares
- Cripto Pulse: sem fonte; frase do Nine0 abaixo de "conteúdo informativo" (55% de opacidade)
- A cada post, o Nine0 reescreve a notícia (padrão L.I.C.A.) e envia texto completo ao grupo VIP
- Hora + (postado) no final de cada texto

Variáveis de ambiente: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
Para o Nine0 e o VIP: ANTHROPIC_API_KEY, TELEGRAM_VIP_CHAT_ID
Opcional: FORCAR_PILAR=0..5 (força um pilar fora do horário)
Teste da arte sem enviar nada: python conteudo_gratuito.py --preview
"""
import os
import re
import sys
import html
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont, ImageFilter

try:
    from nine0_cripto import frase_nine0, _nine0, enviar_vip
except Exception as _e:  # sem o Nine0 o conteúdo gratuito continua saindo
    print("Nine0 indisponível (nine0_cripto.py não encontrado):", _e)

    def frase_nine0(titulo, resumo):
        return "Paciência é a forma mais elegante de estar certo no tempo certo."

    def _nine0(prompt, max_tokens=900):
        return ""

    def enviar_vip(texto):
        print("VIP indisponível")

FUSO = ZoneInfo("America/Sao_Paulo")
LAT, LON = -31.77, -52.34  # Pelotas/RS
LIMITE_LEGENDA = 1000  # Telegram aceita 1024; fica uma folga
LIMITE_VIP = 4000      # Telegram aceita 4096
ALFA_FRASE = int(255 * 0.55)  # frase do Nine0 com 55% de opacidade
VIP_PILARES = {0, 1, 2, 3, 4, 5}  # pilares que também geram texto para o VIP
AVISO = "⚠️ Conteúdo informativo, não é recomendação de investimento."

PILARES = [
    {"nome": "🪙 Cripto Pulse", "arte": "CRIPTO PULSE", "tipo": "rss",
     "rss": "https://www.coindesk.com/arc/outboundfeeds/rss/", "idioma": "en",
     "fonte": "CoinDesk", "cor": (247, 160, 40), "motivo": "moeda", "sem_fonte": True},
    {"nome": "🇧🇷 Termômetro BR", "arte": "TERMÔMETRO BR", "tipo": "rss",
     "rss": "https://g1.globo.com/rss/g1/economia/", "idioma": "pt",
     "fonte": "g1 Economia", "cor": (46, 204, 113), "motivo": "medidor"},
    {"nome": "🌍 Giro Global", "arte": "GIRO GLOBAL", "tipo": "rss",
     "rss": "http://feeds.bbci.co.uk/news/business/rss.xml", "idioma": "en",
     "fonte": "BBC News", "cor": (64, 160, 255), "motivo": "globo"},
    {"nome": "📈 Sala de Trade", "arte": "SALA DE TRADE", "tipo": "rss",
     "rss": "https://www.investing.com/rss/news.rss", "idioma": "en",
     "fonte": "Investing.com", "cor": (160, 100, 255), "motivo": "candles"},
    {"nome": "🤖 Radar IA", "arte": "RADAR IA", "tipo": "rss",
     "rss": "https://techcrunch.com/category/artificial-intelligence/feed/", "idioma": "en",
     "fonte": "TechCrunch", "cor": (0, 220, 255), "motivo": "rede"},
    {"nome": "🌦️ Clima & Mercado", "arte": "CLIMA & MERCADO", "tipo": "clima", "idioma": "pt",
     "fonte": "Open-Meteo", "cor": (255, 176, 46), "motivo": "sol", "rotulo_extras": "Próximos dias"},
]

# hora UTC -> índice do pilar (Brasília = UTC-3)
# 05h Clima, 08h Sala de Trade, 10h Radar IA, 14h Termômetro BR, 16h Giro Global, 21h Cripto Pulse
HORARIOS_UTC = {8: 5, 11: 3, 13: 4, 17: 1, 19: 2, 0: 0}

W, H = 1080, 1350
MARGEM = 80
BRANCO = (240, 244, 252)
CINZA = (160, 172, 196)
DOURADO = (214, 175, 60)

FONTES_BOLD = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
               "C:/Windows/Fonts/arialbd.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"]
FONTES_REG = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              "C:/Windows/Fonts/arial.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf"]
FONTES_OBL = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
              "C:/Windows/Fonts/ariali.ttf", "/System/Library/Fonts/Supplemental/Arial Italic.ttf"]


def fonte(caminhos, tam):
    for c in caminhos:
        if os.path.exists(c):
            return ImageFont.truetype(c, tam)
    return ImageFont.load_default()


# ------------------------------------------------------------------ texto
def limpar_html(texto):
    texto = re.sub(r"<[^>]+>", " ", texto or "")
    texto = html.unescape(texto)
    return re.sub(r"\s+", " ", texto).strip()


def so_caracteres_da_fonte(texto):
    """Tira emojis e símbolos que a fonte da imagem não desenha."""
    return "".join(c for c in texto
                   if not (0x1F000 <= ord(c) <= 0x1FFFF or 0x2600 <= ord(c) <= 0x27BF or ord(c) == 0xFE0F)).strip()


def resumir(texto, limite):
    """Resumo que termina em fim de frase (ou em palavra inteira). Nunca corta no meio."""
    texto = (texto or "").strip()
    if len(texto) <= limite:
        return texto
    corte = texto[:limite]
    fins = [m.end() for m in re.finditer(r"[.!?](?=\s|$)", corte)]
    if fins and fins[-1] >= limite * 0.45:
        return corte[:fins[-1]].strip()
    return corte.rsplit(" ", 1)[0].rstrip(",;:-–—") + "…"


def traduzir(texto, idioma_origem):
    if idioma_origem == "pt" or not texto:
        return texto
    try:
        resp = requests.get("https://api.mymemory.translated.net/get",
                            params={"q": resumir(texto, 480), "langpair": f"{idioma_origem}|pt-BR"}, timeout=20)
        resp.raise_for_status()
        t = resp.json()["responseData"]["translatedText"] or ""
        if not t or "MYMEMORY WARNING" in t.upper():
            return texto
        return html.unescape(t)
    except Exception:
        return texto


# ------------------------------------------------------------------ fontes de conteúdo
def buscar_noticias(url, idioma):
    resp = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    itens = ET.fromstring(resp.content).findall(".//item")
    if not itens:
        return None
    p = itens[0]
    titulo = limpar_html(p.findtext("title", default=""))
    descricao = limpar_html(p.findtext("description", default=""))
    if descricao.lower().startswith(titulo.lower()[:40]):
        descricao = ""  # descrição que só repete o título não ajuda
    return {"titulo": traduzir(titulo, idioma),
            "resumo": traduzir(descricao, idioma) if descricao else "",
            "extras": []}


ROTULOS_CLIMA = {"sol": "Céu limpo", "parcial": "Parcialmente nublado", "nublado": "Nublado",
                 "chuva": "Chuva", "tempestade": "Tempestade", "neblina": "Neblina"}
DIAS_SEMANA = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]


def classificar_clima(codigo):
    """Código WMO do Open-Meteo -> tipo simples usado na arte."""
    if codigo in (95, 96, 99):
        return "tempestade"
    if codigo in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 71, 73, 75, 77, 80, 81, 82, 85, 86):
        return "chuva"
    if codigo in (45, 48):
        return "neblina"
    if codigo == 3:
        return "nublado"
    if codigo in (1, 2):
        return "parcial"
    if codigo == 0:
        return "sol"
    return "nublado"


def buscar_clima():
    resp = requests.get(
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={LAT}&longitude={LON}"
        "&current=temperature_2m,weather_code,wind_speed_10m,is_day"
        "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,"
        "precipitation_probability_max,wind_gusts_10m_max"
        "&forecast_days=4&timezone=America%2FSao_Paulo", timeout=20)
    resp.raise_for_status()
    j = resp.json()
    d, cur = j["daily"], j["current"]

    tipo_agora = classificar_clima(cur.get("weather_code", 0))
    tipo_dia = classificar_clima(d["weather_code"][0])
    noite = cur.get("is_day", 1) == 0
    tmax, tmin = d["temperature_2m_max"][0], d["temperature_2m_min"][0]
    chuva = d["precipitation_sum"][0] or 0
    prob = d["precipitation_probability_max"][0] or 0
    rajada = d["wind_gusts_10m_max"][0] or 0
    total3 = sum((x or 0) for x in d["precipitation_sum"][:3])

    # alerta (baseado no modelo de previsão; não substitui avisos oficiais)
    alerta = None
    if tipo_dia == "tempestade":
        alerta = "ATENÇÃO: possibilidade de tempestade hoje"
    elif chuva >= 30:
        alerta = f"ATENÇÃO: chuva forte prevista ({chuva:.0f} mm)"
    elif rajada >= 60:
        alerta = f"ATENÇÃO: rajadas de vento até {rajada:.0f} km/h"

    nota = ""
    if total3 < 2:
        nota = "Pouquíssima chuva nos próximos dias: atenção às lavouras da região."
    elif total3 > 60:
        nota = "Volume alto de chuva previsto: risco de excesso hídrico no campo."

    faixa = alerta or nota or "Sem alertas relevantes na previsão dos próximos dias."
    tipo_cena = "tempestade" if alerta and tipo_dia == "tempestade" else tipo_agora
    if tipo_agora in ("sol", "parcial", "nublado") and tipo_dia == "tempestade":
        tipo_cena = "tempestade"  # o dia tem risco de temporal: a arte avisa

    clima = {
        "tipo": tipo_cena, "noite": noite, "rotulo": ROTULOS_CLIMA[tipo_cena],
        "agora": cur["temperature_2m"], "vento": cur.get("wind_speed_10m") or 0,
        "tmax": tmax, "tmin": tmin, "chuva": chuva, "prob": prob, "rajada": rajada,
        "total3": total3, "alerta": alerta, "faixa": faixa,
        "dias": [],
    }
    for i in range(1, 4):
        dt = datetime.fromisoformat(d["time"][i])
        clima["dias"].append({
            "dia": DIAS_SEMANA[dt.weekday()], "tipo": classificar_clima(d["weather_code"][i]),
            "tmax": d["temperature_2m_max"][i], "tmin": d["temperature_2m_min"][i],
            "chuva": d["precipitation_sum"][i] or 0,
        })

    resumo = (f"Agora: {cur['temperature_2m']:.0f}°C, {ROTULOS_CLIMA[tipo_agora].lower()}. "
              f"Hoje: mínima de {tmin:.0f}°C e máxima de {tmax:.0f}°C, chuva de {chuva:.0f} mm "
              f"(probabilidade de {prob:.0f}%). Rajadas de até {rajada:.0f} km/h.")
    if alerta:
        resumo += f" ⚠️ {alerta.replace('ATENÇÃO: ', '').capitalize()}."
    elif nota:
        resumo += f" ⚠️ {nota}"
    extras = [f"{x['dia']}: {x['tmin']:.0f}° a {x['tmax']:.0f}°C, chuva {x['chuva']:.0f} mm "
              f"({ROTULOS_CLIMA[x['tipo']].lower()})" for x in clima["dias"]]
    return {"titulo": "Previsão do tempo em Pelotas/RS", "resumo": resumo, "extras": extras, "clima": clima}


# ------------------------------------------------------------------ arte (sem logo, sem direitos de terceiros)
def mistura(c, k):
    return tuple(int(v * k) for v in c)


def fundo(cor):
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    topo, base = (7, 10, 30), mistura(cor, 0.22)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(topo[i] + (base[i] - topo[i]) * t) for i in range(3)))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    g = ImageDraw.Draw(glow)
    g.ellipse([560, -260, 1360, 540], fill=cor + (115,))
    g.ellipse([-320, 900, 560, 1700], fill=cor + (70,))
    glow = glow.filter(ImageFilter.GaussianBlur(120))
    img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
    d = ImageDraw.Draw(img, "RGBA")
    for x in range(0, W, 72):
        d.line([(x, 0), (x, H)], fill=(255, 255, 255, 8))
    for y in range(0, H, 72):
        d.line([(0, y), (W, y)], fill=(255, 255, 255, 8))
    return img


def motivo(img, tipo, cor):
    """Desenho temático no canto superior direito (formas simples, só código)."""
    d = ImageDraw.Draw(img, "RGBA")
    x0, y0, s = 700, 70, 300  # caixa 300x300
    cx, cy = x0 + s // 2, y0 + s // 2
    forte, suave = cor + (230,), cor + (90,)
    if tipo == "moeda":
        d.ellipse([x0, y0, x0 + s, y0 + s], outline=forte, width=10)
        d.ellipse([x0 + 40, y0 + 40, x0 + s - 40, y0 + s - 40], outline=suave, width=6)
        d.line([(cx - 50, cy), (cx + 50, cy)], fill=forte, width=10)
        d.line([(cx, cy - 50), (cx, cy + 50)], fill=forte, width=10)
    elif tipo == "medidor":
        d.arc([x0, y0 + 40, x0 + s, y0 + s + 40], 180, 360, fill=suave, width=22)
        d.arc([x0, y0 + 40, x0 + s, y0 + s + 40], 180, 285, fill=forte, width=22)
        d.line([(cx, cy + 40), (cx + 70, cy - 70)], fill=BRANCO + (255,), width=8)
        d.ellipse([cx - 14, cy + 26, cx + 14, cy + 54], fill=BRANCO + (255,))
    elif tipo == "globo":
        d.ellipse([x0, y0, x0 + s, y0 + s], outline=forte, width=8)
        d.ellipse([x0 + 75, y0, x0 + s - 75, y0 + s], outline=suave, width=5)
        d.ellipse([x0 + 140, y0, x0 + s - 140, y0 + s], outline=suave, width=5)
        for dy in (-80, 0, 80):
            d.line([(x0 + 14, cy + dy), (x0 + s - 14, cy + dy)], fill=suave, width=4)
    elif tipo == "candles":
        dados = [(60, 150, 1), (90, 200, 0), (120, 230, 1), (70, 180, 0), (150, 270, 1), (110, 240, 1)]
        for i, (a, b, alta) in enumerate(dados):
            x = x0 + 14 + i * 50
            d.line([(x + 15, y0 + s - b - 25), (x + 15, y0 + s - a + 25)], fill=suave, width=4)
            d.rectangle([x, y0 + s - b, x + 30, y0 + s - a], fill=(forte if alta else suave))
    elif tipo == "rede":
        pts = [(x0 + 30, y0 + 220), (x0 + 110, y0 + 90), (x0 + 200, y0 + 190), (x0 + 270, y0 + 60), (x0 + 150, y0 + 20)]
        for a, b in [(0, 1), (1, 2), (2, 3), (1, 4), (3, 4)]:
            d.line([pts[a], pts[b]], fill=suave, width=5)
        for (px, py) in pts:
            d.ellipse([px - 18, py - 18, px + 18, py + 18], fill=forte)
    elif tipo == "sol":
        halo = Image.new("RGBA", img.size, (0, 0, 0, 0))
        hd = ImageDraw.Draw(halo)
        hd.ellipse([cx - 150, cy - 150, cx + 150, cy + 150], fill=cor + (70,))
        halo = halo.filter(ImageFilter.GaussianBlur(40))
        img.paste(Image.alpha_composite(img.convert("RGBA"), halo).convert("RGB"))
        d = ImageDraw.Draw(img, "RGBA")
        d.ellipse([cx - 70, cy - 70, cx + 70, cy + 70], fill=cor + (235,))


def quebrar(d, texto, fnt, largura):
    linhas, atual = [], ""
    for palavra in texto.split():
        teste = (atual + " " + palavra).strip()
        if d.textlength(teste, font=fnt) <= largura:
            atual = teste
        else:
            linhas.append(atual)
            atual = palavra
    if atual:
        linhas.append(atual)
    return linhas


def ajustar(d, texto, tamanhos, bold, largura, max_linhas):
    """Escolhe o maior tamanho em que o texto cabe; se não couber, resume em frase inteira."""
    caminhos = FONTES_BOLD if bold else FONTES_REG
    limite = len(texto)
    while True:
        t = resumir(texto, limite)
        for tam in tamanhos:
            f = fonte(caminhos, tam)
            linhas = quebrar(d, t, f, largura)
            if len(linhas) <= max_linhas:
                return f, linhas
        if limite <= 40:
            return f, linhas[:max_linhas]
        limite = int(limite * 0.85)


def desenhar_frase(d, frase, x, y):
    """Frase do Nine0: itálico, filete dourado à esquerda, 55% de opacidade, até 2 linhas."""
    frase = so_caracteres_da_fonte(frase)
    larg = W - 2 * MARGEM - 170  # deixa espaço para o L.I.C.A. à direita
    tam, f, linhas = 26, None, []
    for tam in (26, 24, 22, 20):
        f = fonte(FONTES_OBL, tam)
        linhas = quebrar(d, frase, f, larg)
        if len(linhas) <= 2:
            break
    linhas = linhas[:2]
    passo = int(tam * 1.3)
    d.rectangle([x, y + 3, x + 4, y + len(linhas) * passo - 3], fill=DOURADO + (ALFA_FRASE,))
    for i, ln in enumerate(linhas):
        d.text((x + 20, y + i * passo), ln, font=f, fill=(255, 255, 255, ALFA_FRASE))


def gerar_arte(pilar, titulo, resumo, agora, clima=None, frase=None):
    if clima:
        return gerar_arte_clima(pilar, clima, agora)
    cor = pilar["cor"]
    img = fundo(cor)
    motivo(img, pilar["motivo"], cor)
    d = ImageDraw.Draw(img, "RGBA")
    larg = W - 2 * MARGEM

    d.rectangle([MARGEM, 90, MARGEM + 110, 96], fill=DOURADO)
    d.text((MARGEM, 120), pilar["arte"], font=fonte(FONTES_BOLD, 46), fill=cor)
    d.text((MARGEM, 186), agora.strftime("%d/%m/%Y  •  %H:%M (Brasília)"), font=fonte(FONTES_REG, 28), fill=CINZA)

    y = 390
    f_tit, linhas_tit = ajustar(d, so_caracteres_da_fonte(titulo), (64, 58, 52, 46), True, larg, 5)
    for ln in linhas_tit:
        d.text((MARGEM, y), ln, font=f_tit, fill=BRANCO)
        y += int(f_tit.size * 1.28)

    y += 26
    d.rectangle([MARGEM, y, MARGEM + 90, y + 5], fill=cor)
    y += 44
    if resumo:
        max_l = max(2, int((H - 190 - y) / 56))
        f_res, linhas_res = ajustar(d, so_caracteres_da_fonte(resumo), (38, 35, 32), False, larg, max_l)
        for ln in linhas_res:
            d.text((MARGEM, y), ln, font=f_res, fill=(214, 222, 238))
            y += int(f_res.size * 1.42)

    d.line([(MARGEM, H - 150), (W - MARGEM, H - 150)], fill=(255, 255, 255, 40), width=1)
    if pilar.get("sem_fonte") and frase:
        # Cripto Pulse: sem fonte; frase do Nine0 logo abaixo de "conteúdo informativo"
        d.text((MARGEM, H - 132), "Conteúdo informativo, não é recomendação de investimento.",
               font=fonte(FONTES_REG, 22), fill=CINZA)
        desenhar_frase(d, frase, MARGEM, H - 92)
    else:
        d.text((MARGEM, H - 112), "Conteúdo informativo, não é recomendação de investimento.",
               font=fonte(FONTES_REG, 22), fill=CINZA)
        if not pilar.get("sem_fonte"):
            d.text((MARGEM, H - 72), f"Fonte: {pilar['fonte']}", font=fonte(FONTES_REG, 24), fill=CINZA)
    d.text((W - MARGEM, H - 76), "L.I.C.A.", font=fonte(FONTES_BOLD, 30), fill=DOURADO, anchor="ra")
    return img


# ------------------------------------------------------------------ arte do clima (sincronizada com o tempo)
CENAS = {  # cor do céu: topo -> base
    "sol": ((255, 190, 70), (235, 115, 45)),
    "parcial": ((100, 170, 235), (50, 100, 180)),
    "nublado": ((120, 135, 160), (55, 65, 92)),
    "chuva": ((55, 105, 175), (18, 38, 88)),
    "tempestade": ((82, 50, 140), (22, 16, 56)),
    "neblina": ((150, 160, 178), (70, 80, 102)),
}
CENA_NOITE = ((18, 32, 78), (8, 14, 40))
ACENTO = {"sol": (255, 176, 46), "parcial": (130, 195, 255), "nublado": (175, 190, 214),
          "chuva": (64, 160, 255), "tempestade": (190, 120, 255), "neblina": (190, 200, 215)}
ESTRELAS = [(150, 330), (260, 290), (420, 340), (520, 300), (610, 380), (880, 300), (940, 400), (700, 640), (200, 600)]


def cartao_degrade(img, caixa, topo, base, raio=36):
    x0, y0, x1, y1 = caixa
    w, h = x1 - x0, y1 - y0
    grad = Image.new("RGB", (w, h))
    gd = ImageDraw.Draw(grad)
    for y in range(h):
        t = y / h
        gd.line([(0, y), (w, y)], fill=tuple(int(topo[i] + (base[i] - topo[i]) * t) for i in range(3)))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=raio, fill=255)
    img.paste(grad, (x0, y0), mask)


def brilho(img, cx, cy, r, cor, alfa=90):
    halo = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(halo).ellipse([cx - r, cy - r, cx + r, cy + r], fill=cor + (alfa,))
    halo = halo.filter(ImageFilter.GaussianBlur(max(8, r // 3)))
    img.paste(Image.alpha_composite(img.convert("RGBA"), halo).convert("RGB"))


def desenho_sol(img, cx, cy, r):
    brilho(img, cx, cy, int(r * 2.2), (255, 200, 80), 110)
    d = ImageDraw.Draw(img, "RGBA")
    import math
    for k in range(12):
        a = math.radians(k * 30)
        d.line([(cx + math.cos(a) * r * 1.35, cy + math.sin(a) * r * 1.35),
                (cx + math.cos(a) * r * 1.8, cy + math.sin(a) * r * 1.8)],
               fill=(255, 214, 110, 230), width=max(3, int(r * 0.12)))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 205, 70, 255))


def desenho_lua(img, cx, cy, r):
    brilho(img, cx, cy, int(r * 2.0), (190, 210, 255), 80)
    mask = Image.new("L", img.size, 0)
    md = ImageDraw.Draw(mask)
    md.ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
    md.ellipse([cx - r * 0.35, cy - r * 1.05, cx + r * 1.65, cy + r * 0.95], fill=0)
    img.paste((235, 240, 255), None, mask)


def desenho_nuvem(img, cx, cy, s, cor):
    d = ImageDraw.Draw(img, "RGBA")
    c = cor + (255,)
    d.rounded_rectangle([cx - 0.6 * s, cy, cx + 0.6 * s, cy + 0.36 * s], radius=int(0.18 * s), fill=c)
    for dx, dy, rr in ((-0.30, 0.02, 0.28), (0.0, -0.12, 0.36), (0.32, 0.04, 0.26)):
        d.ellipse([cx + dx * s - rr * s, cy + dy * s - rr * s, cx + dx * s + rr * s, cy + dy * s + rr * s], fill=c)


def desenho_chuva(img, cx, cy, s, n=6):
    d = ImageDraw.Draw(img, "RGBA")
    for i in range(n):
        x = cx - 0.45 * s + i * 0.18 * s
        y = cy + 0.46 * s + (i % 2) * 0.12 * s
        d.line([(x, y), (x - 0.09 * s, y + 0.28 * s)], fill=(110, 185, 255, 235), width=max(3, int(s * 0.03)))


def desenho_raio(img, cx, cy, s):
    d = ImageDraw.Draw(img, "RGBA")
    pts = [(0.08, 0.30), (-0.14, 0.76), (0.0, 0.76), (-0.12, 1.20), (0.26, 0.62), (0.09, 0.62), (0.22, 0.30)]
    d.polygon([(cx + x * s, cy + y * s) for x, y in pts], fill=(255, 224, 70, 255))


def icone(img, tipo, noite, cx, cy, s):
    """Ícone do tempo desenhado só com formas (sem imagens de terceiros)."""
    astro_noite = noite and tipo in ("sol", "parcial")
    if tipo == "sol":
        (desenho_lua(img, cx, cy, int(s * 0.5)) if astro_noite else desenho_sol(img, cx, cy, int(s * 0.34)))
    elif tipo == "parcial":
        (desenho_lua(img, int(cx - s * 0.2), int(cy - s * 0.2), int(s * 0.3)) if astro_noite
         else desenho_sol(img, int(cx - s * 0.22), int(cy - s * 0.2), int(s * 0.24)))
        desenho_nuvem(img, cx + int(s * 0.08), cy + int(s * 0.08), s * 0.8, (236, 241, 250))
    elif tipo == "nublado":
        desenho_nuvem(img, cx - int(s * 0.18), cy - int(s * 0.12), s * 0.62, (168, 180, 202))
        desenho_nuvem(img, cx + int(s * 0.1), cy + int(s * 0.08), s * 0.82, (226, 233, 246))
    elif tipo == "chuva":
        desenho_nuvem(img, cx, cy - int(s * 0.18), s * 0.9, (156, 170, 200))
        desenho_chuva(img, cx, cy - int(s * 0.18), s * 0.9)
    elif tipo == "tempestade":
        desenho_nuvem(img, cx, cy - int(s * 0.22), s * 0.9, (104, 104, 150))
        desenho_chuva(img, cx + int(s * 0.2), cy - int(s * 0.22), s * 0.7, n=4)
        desenho_raio(img, cx - int(s * 0.05), cy - int(s * 0.22), s * 0.9)
    else:  # neblina
        desenho_nuvem(img, cx, cy - int(s * 0.18), s * 0.85, (206, 214, 228))
        d = ImageDraw.Draw(img, "RGBA")
        for k in range(3):
            y = cy + int(s * 0.34) + k * int(s * 0.12)
            d.line([(cx - s * 0.5, y), (cx + s * 0.5, y)], fill=(206, 214, 228, 220), width=max(3, int(s * 0.04)))


def gerar_arte_clima(pilar, c, agora):
    tipo, noite = c["tipo"], c["noite"]
    ceu_noturno = noite and tipo in ("sol", "parcial")
    topo, base = CENA_NOITE if ceu_noturno else CENAS[tipo]
    cor = (150, 190, 255) if ceu_noturno else ACENTO[tipo]
    img = fundo(cor)
    d = ImageDraw.Draw(img, "RGBA")

    # cabeçalho no padrão L.I.C.A.
    d.rectangle([MARGEM, 90, MARGEM + 110, 96], fill=DOURADO)
    d.text((MARGEM, 120), pilar["arte"], fon
