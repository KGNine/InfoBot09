#!/usr/bin/env python3
"""
L.I.C.A. | Cripto Pulse (cotações) — versão nova
- Dados: CoinGecko (API pública, sem chave)
- Imagem gerada no código (Pillow): sem logo e sem direitos autorais de ninguém
- Envia foto + legenda ao Telegram (legenda sempre <= 1024 caracteres)

Variáveis de ambiente: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
Teste local sem enviar nada:  python crypto_update.py --preview
"""
import os
import sys
import time
import io
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ---------------------------------------------------------------- configuração
MOEDAS = [  # id no CoinGecko, ticker, nome, cor do selo (só uma cor, sem logo)
    ("bitcoin", "BTC", "Bitcoin", (247, 147, 26)),
    ("ethereum", "ETH", "Ethereum", (118, 140, 240)),
    ("binancecoin", "BNB", "BNB", (243, 186, 47)),
    ("solana", "SOL", "Solana", (153, 69, 255)),
    ("ripple", "XRP", "XRP", (80, 200, 220)),
]
IGNORAR_NAS_ALTAS_E_QUEDAS = {
    "usdt", "usdc", "dai", "fdusd", "usde", "tusd", "usds", "usdd", "pyusd",
    "busd", "usd1", "steth", "wsteth", "weth", "wbtc", "weeth", "cbbtc", "wbeth",
}
FUSO = ZoneInfo("America/Sao_Paulo")
W, H = 1080, 1350
MARGEM = 54

VERDE = (46, 224, 140)
VERMELHO = (255, 82, 108)
BRANCO = (240, 244, 252)
CINZA = (160, 172, 196)
DOURADO = (214, 175, 60)

FONTES_BOLD = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]
FONTES_REG = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
]


def fonte(caminhos, tam):
    for c in caminhos:
        if os.path.exists(c):
            return ImageFont.truetype(c, tam)
    return ImageFont.load_default()


# ---------------------------------------------------------------- formatação PT-BR
def _pt(txt):
    # troca separadores do formato en-US para pt-BR
    return txt.replace(",", "§").replace(".", ",").replace("§", ".")


def money_compacto(v):
    if v is None:
        return "-"
    for lim, suf in ((1e12, "tri"), (1e9, "bi"), (1e6, "mi")):
        if v >= lim:
            return "US$ " + _pt(f"{v / lim:,.2f}") + f" {suf}"
    return "US$ " + _pt(f"{v:,.0f}")


def preco(v):
    if v is None:
        return "-"
    if v >= 1000:
        return "US$ " + _pt(f"{v:,.0f}")
    if v >= 1:
        return "US$ " + _pt(f"{v:,.2f}")
    return "US$ " + _pt(f"{v:,.4f}")


def pct(v):
    if v is None:
        return "-"
    return ("+" if v >= 0 else "") + _pt(f"{v:.2f}") + "%"


# ---------------------------------------------------------------- dados
def get_json(url, params=None, tentativas=4):
    ultimo = None
    for i in range(tentativas):
        try:
            r = requests.get(url, params=params, timeout=30,
                             headers={"User-Agent": "LICA-CriptoPulse/2.0"})
            if r.status_code == 200:
                return r.json()
            ultimo = f"HTTP {r.status_code}"
        except requests.RequestException as e:
            ultimo = str(e)
        time.sleep(5 * (i + 1))  # espera crescente (CoinGecko limita chamadas)
    raise RuntimeError(f"Falha ao buscar {url}: {ultimo}")


def buscar_dados():
    mercado = get_json(
        "https://api.coingecko.com/api/v3/coins/markets",
        {"vs_currency": "usd", "order": "market_cap_desc", "per_page": 100,
         "page": 1, "sparkline": "false", "price_change_percentage": "24h"},
    )
    glob = get_json("https://api.coingecko.com/api/v3/global")["data"]
    por_id = {m["id"]: m for m in mercado}

    principais = []
    for cid, tick, nome, cor in MOEDAS:
        m = por_id.get(cid)
        if not m:
            continue
        principais.append({
            "ticker": tick, "nome": nome, "cor": cor,
            "preco": m["current_price"], "var": m.get("price_change_percentage_24h"),
            "mcap": m.get("market_cap"), "vol": m.get("total_volume"),
        })

    candidatas = [
        m for m in mercado
        if m["symbol"].lower() not in IGNORAR_NAS_ALTAS_E_QUEDAS
        and m.get("price_change_percentage_24h") is not None
    ]
    ordenadas = sorted(candidatas, key=lambda m: m["price_change_percentage_24h"])
    quedas = [(m["symbol"].upper(), m["price_change_percentage_24h"]) for m in ordenadas[:3]]
    altas = [(m["symbol"].upper(), m["price_change_percentage_24h"]) for m in ordenadas[::-1][:3]]

    return {
        "principais": principais,
        "altas": altas,
        "quedas": quedas,
        "mcap_total": glob["total_market_cap"]["usd"],
        "vol_total": glob["total_volume"]["usd"],
        "dom_btc": glob["market_cap_percentage"].get("btc"),
        "var_mcap": glob.get("market_cap_change_percentage_24h_usd"),
    }


def dados_exemplo():
    """Dados fictícios só para testar a imagem (--preview). Não são cotações reais."""
    pr = []
    ex = [("BTC", "Bitcoin", (247, 147, 26), 67432.1, 2.31, 1.33e12, 31.2e9),
          ("ETH", "Ethereum", (118, 140, 240), 3120.55, -1.12, 375e9, 14.8e9),
          ("BNB", "BNB", (243, 186, 47), 585.4, 0.45, 85e9, 1.9e9),
          ("SOL", "Solana", (153, 69, 255), 148.77, 4.87, 69e9, 3.4e9),
          ("XRP", "XRP", (80, 200, 220), 0.5312, -0.78, 30e9, 1.1e9)]
    for t, n, c, p, v, mc, vo in ex:
        pr.append({"ticker": t, "nome": n, "cor": c, "preco": p, "var": v, "mcap": mc, "vol": vo})
    return {
        "principais": pr,
        "altas": [("AAA", 12.4), ("BBB", 9.8), ("CCC", 7.1)],
        "quedas": [("DDD", -8.6), ("EEE", -6.2), ("FFF", -5.4)],
        "mcap_total": 2.41e12, "vol_total": 98.2e9, "dom_btc": 54.1, "var_mcap": 1.2,
    }


# ---------------------------------------------------------------- imagem
def fundo():
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    topo, base = (6, 9, 34), (44, 12, 82)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(topo[i] + (base[i] - topo[i]) * t) for i in range(3)))

    # brilhos neon (círculos desfocados)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    g = ImageDraw.Draw(glow)
    g.ellipse([-250, -200, 550, 520], fill=(0, 190, 255, 120))
    g.ellipse([600, 450, 1350, 1150], fill=(255, 0, 140, 90))
    g.ellipse([100, 950, 800, 1600], fill=(120, 60, 255, 100))
    glow = glow.filter(ImageFilter.GaussianBlur(130))
    img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")

    # grade sutil
    d = ImageDraw.Draw(img, "RGBA")
    for x in range(0, W, 72):
        d.line([(x, 0), (x, H)], fill=(255, 255, 255, 9))
    for y in range(0, H, 72):
        d.line([(0, y), (W, y)], fill=(255, 255, 255, 9))
    return img


def cartao(d, x0, y0, x1, y1, raio=28):
    d.rounded_rectangle([x0, y0, x1, y1], radius=raio, fill=(255, 255, 255, 20),
                        outline=(255, 255, 255, 55), width=2)


def desenhar_imagem(dados, agora):
    img = fundo()
    d = ImageDraw.Draw(img, "RGBA")
    f_tit = fonte(FONTES_BOLD, 66)
    f_sub = fonte(FONTES_REG, 28)
    f_lab = fonte(FONTES_REG, 24)
    f_val = fonte(FONTES_BOLD, 38)
    f_sim = fonte(FONTES_BOLD, 38)
    f_nome = fonte(FONTES_REG, 24)
    f_preco = fonte(FONTES_BOLD, 40)
    f_peq = fonte(FONTES_REG, 22)
    f_pill = fonte(FONTES_BOLD, 30)
    f_ass = fonte(FONTES_BOLD, 28)
    f_rodape = fonte(FONTES_REG, 25)

    # cabeçalho
    d.rectangle([MARGEM, 62, MARGEM + 110, 68], fill=DOURADO)
    d.text((MARGEM, 90), "CRIPTO PULSE", font=f_tit, fill=BRANCO)
    d.text((MARGEM, 172), agora.strftime("%d/%m/%Y  •  %H:%M (Brasília)"), font=f_sub, fill=CINZA)
    d.text((W - MARGEM, 110), "L.I.C.A.", font=f_ass, fill=DOURADO, anchor="ra")

    # resumo global (3 cartões)
    y0, y1 = 236, 366
    larg = (W - 2 * MARGEM - 2 * 20) // 3
    resumo = [
        ("MARKET CAP", money_compacto(dados["mcap_total"])),
        ("VOLUME 24H", money_compacto(dados["vol_total"])),
        ("DOMINÂNCIA BTC", (_pt(f"{dados['dom_btc']:.1f}") + "%") if dados["dom_btc"] else "-"),
    ]
    for i, (rot, val) in enumerate(resumo):
        x0 = MARGEM + i * (larg + 20)
        cartao(d, x0, y0, x0 + larg, y1)
        d.text((x0 + 22, y0 + 24), rot, font=f_lab, fill=CINZA)
        tam = 38 if len(val) < 14 else 31
        d.text((x0 + 22, y0 + 70), val, font=fonte(FONTES_BOLD, tam), fill=BRANCO)

    # tabela das 5 principais
    ty0, ty1 = 392, 392 + 5 * 104 + 24
    cartao(d, MARGEM, ty0, W - MARGEM, ty1)
    for i, m in enumerate(dados["principais"][:5]):
        y = ty0 + 12 + i * 104
        if i > 0:
            d.line([(MARGEM + 28, y), (W - MARGEM - 28, y)], fill=(255, 255, 255, 28), width=1)
        cx, cy = MARGEM + 62, y + 52
        d.ellipse([cx - 30, cy - 30, cx + 30, cy + 30], fill=m["cor"] + (255,))
        d.text((cx, cy), m["ticker"][0], font=f_sim, fill=(10, 14, 30), anchor="mm")
        d.text((MARGEM + 112, y + 16), m["ticker"], font=f_val, fill=BRANCO)
        d.text((MARGEM + 112, y + 62), m["nome"], font=f_nome, fill=CINZA)
        d.text((W - MARGEM - 250, y + 14), preco(m["preco"]), font=f_preco, fill=BRANCO, anchor="ra")
        sub = f"Cap {money_compacto(m['mcap']).replace('US$ ', '')}  •  Vol {money_compacto(m['vol']).replace('US$ ', '')}"
        d.text((W - MARGEM - 250, y + 66), sub, font=f_peq, fill=CINZA, anchor="ra")
        # selo da variação
        cor = VERDE if (m["var"] or 0) >= 0 else VERMELHO
        px0, px1 = W - MARGEM - 222, W - MARGEM - 28
        d.rounded_rectangle([px0, y + 22, px1, y + 82], radius=30, fill=cor + (46,), outline=cor + (180,), width=2)
        seta = "▲" if (m["var"] or 0) >= 0 else "▼"
        d.text(((px0 + px1) / 2, y + 52), f"{seta} {pct(m['var'])}", font=f_pill, fill=cor, anchor="mm")

    # altas e quedas
    gy0, gy1 = ty1 + 26, ty1 + 26 + 262
    meia = (W - 2 * MARGEM - 20) // 2
    blocos = [("▲  MAIORES ALTAS 24H", VERDE, dados["altas"], MARGEM),
              ("▼  MAIORES QUEDAS 24H", VERMELHO, dados["quedas"], MARGEM + meia + 20)]
    for titulo, cor, itens, x0 in blocos:
        cartao(d, x0, gy0, x0 + meia, gy1)
        d.text((x0 + 26, gy0 + 22), titulo, font=fonte(FONTES_BOLD, 27), fill=cor)
        for j, (tick, v) in enumerate(itens[:3]):
            yy = gy0 + 84 + j * 56
            d.text((x0 + 26, yy), tick, font=fonte(FONTES_BOLD, 34), fill=BRANCO)
            d.text((x0 + meia - 26, yy), pct(v), font=fonte(FONTES_BOLD, 34), fill=cor, anchor="ra")

    # rodapé
    d.line([(MARGEM, H - 104), (W - MARGEM, H - 104)], fill=(255, 255, 255, 40), width=1)
    d.text((W / 2, H - 70), f"Atualizado às {agora.strftime('%H:%M')} (Brasília)  •  Dados ao vivo do grupo L.I.C.A.",
           font=f_rodape, fill=BRANCO, anchor="mm")
    d.text((W / 2, H - 34), "Conteúdo informativo, não é recomendação de investimento.",
           font=fonte(FONTES_REG, 20), fill=CINZA, anchor="mm")
    return img


# ---------------------------------------------------------------- legenda
def montar_legenda(dados, agora):
    emojis = {"BTC": "🟠", "ETH": "🔷", "BNB": "🟡", "SOL": "🟣", "XRP": "⚪"}
    linhas = [
        f"🪙 <b>Cripto Pulse | L.I.C.A.</b> — {agora.strftime('%d/%m %H:%M')}",
        "",
        f"💰 Market cap: {money_compacto(dados['mcap_total'])}",
        f"📊 Volume 24h: {money_compacto(dados['vol_total'])}",
        "",
    ]
    for m in dados["principais"]:
        seta = "📈" if (m["var"] or 0) >= 0 else "📉"
        linhas.append(f"{emojis.get(m['ticker'], '🔹')} <b>{m['ticker']}</b> {preco(m['preco'])} {seta} {pct(m['var'])}")
    linhas += [
        "",
        "🚀 Altas: " + " · ".join(f"{t} {pct(v)}" for t, v in dados["altas"]),
        "🔻 Quedas: " + " · ".join(f"{t} {pct(v)}" for t, v in dados["quedas"]),
        "",
        f"🕐 Atualizado às {agora.strftime('%H:%M')} (Brasília) • Dados ao vivo do grupo L.I.C.A.",
        "⚠️ Conteúdo informativo, não é recomendação de investimento.",
    ]
    texto = "\n".join(linhas)
    return texto if len(texto) <= 1024 else texto[:1020] + "..."


# ---------------------------------------------------------------- envio
def enviar_foto(img, legenda):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat = os.environ["TELEGRAM_CHAT_ID"]
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendPhoto",
        data={"chat_id": chat, "caption": legenda, "parse_mode": "HTML"},
        files={"photo": ("cripto_pulse.png", buf, "image/png")},
        timeout=60,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Telegram respondeu {r.status_code}: {r.text[:300]}")
    print("Enviado com sucesso.")


def main():
    agora = datetime.now(FUSO)
    if "--preview" in sys.argv:
        dados = dados_exemplo()
        img = desenhar_imagem(dados, agora)
        img.save("preview.png")
        print(montar_legenda(dados, agora))
        print("\nImagem de teste salva em preview.png (dados fictícios).")
        return
    dados = buscar_dados()
    img = desenhar_imagem(dados, agora)
    enviar_foto(img, montar_legenda(dados, agora))


if __name__ == "__main__":
    main()
