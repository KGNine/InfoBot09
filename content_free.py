#!/usr/bin/env python3
"""
L.I.C.A. | Conteúdo gratuito (6 pilares, 1 por horário)
Mudanças desta versão:
- Arte própria gerada no código (sem logo de emissora ou marca de ninguém)
- Resumo que nunca corta no meio da frase (cabe na imagem e na legenda)
- Mais conteúdo por post: manchete + resumo + "Também em pauta" (outras manchetes)
- Horário em Brasília e janela de tolerância (se o disparo atrasar, ainda publica)
- Envio em HTML (acentos e símbolos não quebram a mensagem)

Variáveis de ambiente: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
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

FUSO = ZoneInfo("America/Sao_Paulo")
LAT, LON = -31.77, -52.34  # Pelotas/RS
LIMITE_LEGENDA = 1000  # Telegram aceita 1024; fica uma folga
AVISO = "⚠️ Conteúdo informativo, não é recomendação de investimento."

PILARES = [
    {"nome": "🪙 Cripto Pulse", "arte": "CRIPTO PULSE", "tipo": "rss",
     "rss": "https://www.coindesk.com/arc/outboundfeeds/rss/", "idioma": "en",
     "fonte": "CoinDesk", "cor": (247, 160, 40), "motivo": "moeda"},
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
     "fonte": "Open-Meteo", "cor": (255, 176, 46), "motivo": "sol"},
]

# hora UTC -> índice do pilar (07h, 09h, 11h, 13h, 15h e 17h em Brasília)
HORARIOS_UTC = {10: 0, 12: 1, 14: 2, 16: 3, 18: 4, 20: 5}

W, H = 1080, 1350
MARGEM = 80
BRANCO = (240, 244, 252)
CINZA = (160, 172, 196)
DOURADO = (214, 175, 60)

FONTES_BOLD = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
               "C:/Windows/Fonts/arialbd.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"]
FONTES_REG = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              "C:/Windows/Fonts/arial.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf"]


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
def buscar_noticias(url, idioma, extras=2):
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
    outros = []
    for it in itens[1:1 + extras]:
        t = limpar_html(it.findtext("title", default=""))
        if t:
            outros.append(traduzir(t, idioma))
    return {"titulo": traduzir(titulo, idioma),
            "resumo": traduzir(descricao, idioma) if descricao else "",
            "extras": outros}


def buscar_clima():
    resp = requests.get(
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={LAT}&longitude={LON}"
        "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
        "&timezone=America%2FSao_Paulo", timeout=20)
    resp.raise_for_status()
    d = resp.json()["daily"]
    tmax, tmin = d["temperature_2m_max"][0], d["temperature_2m_min"][0]
    chuva_hoje = d["precipitation_sum"][0]
    total3 = sum(d["precipitation_sum"][:3])
    texto = f"Hoje: mínima de {tmin:.0f}°C e máxima de {tmax:.0f}°C, chuva prevista de {chuva_hoje:.0f} mm."
    if total3 < 2:
        texto += " ⚠️ Pouquíssima chuva nos próximos dias: atenção às lavouras da região."
    elif total3 > 60:
        texto += " ⚠️ Volume alto de chuva previsto: risco de excesso hídrico no campo."
    return {"titulo": "Previsão do tempo em Pelotas/RS", "resumo": texto, "extras": []}


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


def gerar_arte(pilar, titulo, resumo, agora):
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
    d.text((MARGEM, H - 112), "Conteúdo informativo, não é recomendação de investimento.",
           font=fonte(FONTES_REG, 22), fill=CINZA)
    d.text((MARGEM, H - 72), f"Fonte: {pilar['fonte']}", font=fonte(FONTES_REG, 24), fill=CINZA)
    d.text((W - MARGEM, H - 76), "L.I.C.A.", font=fonte(FONTES_BOLD, 30), fill=DOURADO, anchor="ra")
    return img


# ------------------------------------------------------------------ legenda e envio
def montar_legenda(pilar, titulo, resumo, extras, agora):
    cab = f"<b>{html.escape(pilar['nome'])}</b> — {agora.strftime('%d/%m %H:%M')} (Brasília)"
    base = [cab, "", f"<b>{html.escape(titulo)}</b>"]
    rodape = ["", f"Fonte: {html.escape(pilar['fonte'])}", AVISO]

    def tam(linhas):
        return len("\n".join(linhas))

    partes = list(base)
    sobra = LIMITE_LEGENDA - tam(base + rodape) - 6
    if resumo and sobra > 80:
        partes += ["", html.escape(resumir(resumo, int(sobra * 0.88)))]
    if extras:
        bloco = ["", "<b>Também em pauta:</b>"]
        for e in extras:
            linha = "▫️ " + html.escape(resumir(e, 140))
            if tam(partes + bloco + [linha] + rodape) <= LIMITE_LEGENDA:
                bloco.append(linha)
        if len(bloco) > 2:
            partes += bloco
    return "\n".join(partes + rodape)


def api(metodo):
    return f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/{metodo}"


def enviar_texto(legenda):
    r = requests.post(api("sendMessage"), data={"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": legenda,
                                                "parse_mode": "HTML", "disable_web_page_preview": "true"}, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"Telegram {r.status_code}: {r.text[:300]}")


def enviar_foto(img, legenda):
    import io
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    r = requests.post(api("sendPhoto"),
                      data={"chat_id": os.environ["TELEGRAM_CHAT_ID"], "caption": legenda, "parse_mode": "HTML"},
                      files={"photo": ("arte.png", buf, "image/png")}, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"Telegram {r.status_code}: {r.text[:300]}")


# ------------------------------------------------------------------ fluxo principal
def escolher_indice(agora_utc):
    h = agora_utc.hour
    if h in HORARIOS_UTC:
        return HORARIOS_UTC[h]
    if (h - 1) in HORARIOS_UTC:  # disparo atrasou: ainda vale o horário anterior
        return HORARIOS_UTC[h - 1]
    return None


def montar_conteudo(pilar):
    if pilar["tipo"] == "clima":
        return buscar_clima()
    return buscar_noticias(pilar["rss"], pilar["idioma"])


def main():
    if "--preview" in sys.argv:
        return preview()

    forcar = os.environ.get("FORCAR_PILAR", "").strip()
    agora_utc = datetime.now(timezone.utc)
    if forcar.isdigit() and int(forcar) < len(PILARES):
        indice = int(forcar)
    else:
        indice = escolher_indice(agora_utc)
    if indice is None:
        print("Hora atual fora do roteiro: nada a enviar.")
        return

    pilar = PILARES[indice]
    agora = agora_utc.astimezone(FUSO)
    try:
        c = montar_conteudo(pilar)
    except Exception as e:
        print("Fonte indisponível:", type(e).__name__, e)
        c = None
    if not c or not c["titulo"]:
        print("Sem conteúdo para este horário; nada enviado (evita post vazio).")
        return

    legenda = montar_legenda(pilar, c["titulo"], c["resumo"], c["extras"], agora)
    try:
        enviar_foto(gerar_arte(pilar, c["titulo"], c["resumo"], agora), legenda)
    except Exception as e:
        print("Falha com imagem, enviando só texto:", e)
        enviar_texto(legenda)
    print("Enviado:", pilar["nome"])
    print(legenda)


def preview():
    """Gera uma arte de teste de cada pilar, com textos de exemplo (não envia nada)."""
    agora = datetime.now(FUSO)
    ex = {
        "titulo": "Dólar fecha em queda e Ibovespa sobe com expectativa sobre os próximos passos dos juros nos EUA e no Brasil",
        "resumo": ("O mercado reagiu ao cenário externo e a moeda americana recuou frente ao real. "
                   "Investidores acompanham a ata do Fed e dados de inflação para calibrar as apostas sobre juros. "
                   "Nos próximos dias, a agenda de indicadores deve concentrar a atenção do mercado."),
        "extras": ["Petróleo recua com sinais de demanda mais fraca", "Bolsas da Europa fecham sem direção única"],
    }
    for i, p in enumerate(PILARES):
        gerar_arte(p, ex["titulo"], ex["resumo"], agora).save(f"preview_{i}.png")
    print(montar_legenda(PILARES[1], ex["titulo"], ex["resumo"], ex["extras"], agora))
    print("\nArtes de teste salvas: preview_0.png ... preview_5.png")


if __name__ == "__main__":
    main()
