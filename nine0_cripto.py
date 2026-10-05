# nine0_cripto.py — Cripto Pulse: frase do Nine0 na arte, texto VIP e carimbo
import os, re, html, textwrap, requests
from datetime import datetime
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw, ImageFont

API_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")
MODELO   = os.environ.get("NINE0_MODELO", "claude-sonnet-5-5")
TOKEN    = os.environ.get("TELEGRAM_BOT_TOKEN", "")
VIP_CHAT = os.environ.get("TELEGRAM_VIP_CHAT_ID", "")
LIMITE_VIP = 4000  # Telegram aceita 4096; folga de segurança

F = "/usr/share/fonts/truetype/dejavu/"
OURO = (212, 175, 55)

FRASES_RESERVA = {
    "alta": "O que sobe sem base logo lembra que a gravidade também é método.",
    "queda": "Quem governa a si mesmo não teme o mercado: teme apenas a pressa.",
    "neutro": "Paciência é a forma mais elegante de estar certo no tempo certo.",
}

def carimbo():
    return datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%H:%M") + " (postado)"

def _nine0(prompt, max_tokens=900):
    if not API_KEY:
        return ""
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": API_KEY, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": MODELO, "max_tokens": max_tokens,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=60)
        r.raise_for_status()
        return "".join(b.get("text", "") for b in r.json()["content"]).strip()
    except Exception as e:
        print("Nine0 indisponível:", e)
        return ""

def frase_nine0(titulo, resumo):
    p = ("Você é o Nine0, a mente filosófica da L.I.C.A. (informação financeira). "
         "Escreva UMA frase filosófica original em português do Brasil, de até 110 "
         "caracteres, que dialogue com o contexto desta notícia cripto, sem citar "
         "autores, sem emojis, sem promessa de ganho e sem aspas. "
         "Responda só com a frase.\n\n"
         f"Título: {titulo}\nResumo: {resumo}")
    f = _nine0(p, 120).strip('"“” \n')
    if f and len(f) <= 130:
        return f
    t = (titulo + " " + resumo).lower()
    chave = "queda" if re.search(r"queda|cai|desaba|recua|perde|liquida", t) else \
            "alta" if re.search(r"alta|sobe|dispara|recorde|avança|ganha", t) else "neutro"
    return FRASES_RESERVA[chave]

def rodape(img, frase):
    """Desenha 'CONTEÚDO INFORMATIVO' + frase do Nine0 (55% de opacidade)."""
    img = img.convert("RGBA")
    W, H = img.size
    camada = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(camada)
    # degradê escuro na base para leitura
    for i in range(260):
        d.line([(0, H - 260 + i), (W, H - 260 + i)], fill=(0, 0, 0, int(150 * i / 260)))
    f_tag = ImageFont.truetype(F + "DejaVuSans-Bold.ttf", int(W * 0.024))
    f_fr = ImageFont.truetype(F + "DejaVuSans-Oblique.ttf", int(W * 0.032))
    tag = "C O N T E Ú D O   I N F O R M A T I V O"
    y = H - int(H * 0.17)
    tw = d.textlength(tag, font=f_tag)
    d.text(((W - tw) / 2, y), tag, font=f_tag, fill=OURO + (255,))
    y += int(W * 0.045)
    d.line([(W * 0.38, y), (W * 0.62, y)], fill=OURO + (200,), width=2)
    y += int(W * 0.03)
    alfa = int(255 * 0.55)  # 55%
    cols = max(18, int(W / (f_fr.size * 0.58)))
    for linha in textwrap.wrap(frase, cols)[:3]:
        lw = d.textlength(linha, font=f_fr)
        d.text(((W - lw) / 2, y), linha, font=f_fr, fill=(255, 255, 255, alfa))
        y += int(f_fr.size * 1.35)
    return Image.alpha_composite(img, camada).convert("RGB")

def texto_vip(titulo, resumo, frase):
    """Texto completo padrão L.I.C.A., reescrito pelo Nine0, com hora (postado)."""
    p = ("Você é o Nine0, a mente criativa da L.I.C.A. (Liquidity Interest Cost "
         "Appreciation). Reescreva a notícia abaixo com outras palavras, SEM perder "
         "o sentido original, no ambiente L.I.C.A.: vocabulário mais inteligente, "
         "tom profissional, claro, sem exageros e sem recomendação de compra ou "
         "venda. Responda neste formato exato, texto puro, sem markdown:\n"
         "TITULO: <título reescrito>\nCORPO: <3 a 5 parágrafos curtos>\n\n"
         f"Título: {titulo}\nNotícia: {resumo}")
    saida = _nine0(p, 1200)
    m = re.search(r"TITULO:\s*(.+?)\s*CORPO:\s*(.+)", saida, re.S)
    t, c = (m.group(1).strip(), m.group(2).strip()) if m else (titulo, resumo)
    fixo = (f"📡 <b>CRIPTO PULSE | L.I.C.A. VIP</b>\n\n<b>{html.escape(t)}</b>\n\n")
    fim = (f"\n\n🧠 <i>{html.escape(frase)}</i>\n\n"
           "⚠️ Conteúdo informativo, não é recomendação de investimento.\n"
           f"🕒 {carimbo()}")
    sobra = LIMITE_VIP - len(fixo) - len(fim)
    c = html.escape(c)
    if len(c) > sobra:
        c = c[:sobra].rsplit(". ", 1)[0].rstrip() + "."
    return fixo + c + fim

def enviar_vip(texto):
    if not (TOKEN and VIP_CHAT):
        print("VIP não configurado: defina TELEGRAM_VIP_CHAT_ID")
        return
    r = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                      data={"chat_id": VIP_CHAT, "text": texto, "parse_mode": "HTML",
                            "disable_web_page_preview": "true"}, timeout=30)
    print("VIP:", r.status_code)
