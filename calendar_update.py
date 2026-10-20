import os
import re
import html
import requests
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

FUSO = ZoneInfo("America/Sao_Paulo")
NY = ZoneInfo("America/New_York")
LIMITE_MSG = 3800  # Telegram aceita 4096

# Calendario global gratuito (Forex Factory / Fair Economy).
# Cobre EUA, Zona do Euro, Japao, Australia, Reino Unido, Canada,
# Nova Zelandia, Suica e China. Nao cobre o Brasil (ver EVENTOS BR).
FEEDS_GLOBAIS = [
    "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
    "https://nfs.faireconomy.media/ff_calendar_nextweek.json",
]

BANDEIRAS = {
    "USD": "🇺🇸", "EUR": "🇪🇺", "JPY": "🇯🇵", "AUD": "🇦🇺",
    "GBP": "🇬🇧", "CAD": "🇨🇦", "NZD": "🇳🇿", "CHF": "🇨🇭",
    "CNY": "🇨🇳", "BRL": "🇧🇷", "ALL": "🌐",
}
DIAS = [
    "Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira",
    "Sexta-feira", "Sábado", "Domingo",
]

# Eventos que valem 5 estrelas quando o calendario os marca como alto
CINCO_ESTRELAS = [
    "federal funds rate", "fomc statement", "main refinancing rate",
    "cash rate", "boj policy rate", "policy rate", "official bank rate",
    "overnight rate", "monetary policy", "non-farm", "cpi",
]

# Traducao dos nomes mais comuns (o resto aparece no original)
TRADUCOES = [
    (r"non-farm employment change",
     "Payroll (empregos fora do setor agrícola)"),
    (r"federal funds rate", "Decisão de juros do Fed"),
    (r"fomc meeting minutes", "Ata do FOMC"),
    (r"fomc statement", "Comunicado do FOMC"),
    (r"fomc press conference", "Coletiva do presidente do Fed"),
    (r"main refinancing rate", "Decisão de juros do BCE"),
    (r"ecb press conference", "Coletiva do BCE"),
    (r"boj policy rate", "Decisão de juros do BoJ"),
    (r"boj press conference", "Coletiva do BoJ"),
    (r"official bank rate", "Decisão de juros do BoE"),
    (r"^cash rate", "Decisão de juros do RBA"),
    (r"rba rate statement", "Comunicado do RBA"),
    (r"unemployment rate", "Taxa de desemprego"),
    (r"core cpi", "CPI núcleo (inflação)"),
    (r"\bcpi\b", "CPI (inflação)"),
    (r"core ppi|\bppi\b", "PPI (preços ao produtor)"),
    (r"retail sales", "Vendas no varejo"),
    (r"\bgdp\b", "PIB"),
    (r"manufacturing pmi", "PMI industrial"),
    (r"services pmi", "PMI de serviços"),
    (r"trade balance", "Balança comercial"),
    (r"employment change", "Variação de empregos"),
    (r"speaks", "discursa"),
    (r"\by/y\b", "a/a"),
    (r"\bm/m\b", "m/m"),
]


def traduzir_titulo(t):
    out = t
    for padrao, pt in TRADUCOES:
        out = re.sub(padrao, pt, out, flags=re.I)
    return out


def estrelas(impacto, titulo):
    # Calendario so tem 3 niveis.
    # alto = 4 (5 se for juros, payroll ou CPI), medio = 3,
    # baixo e feriado = 0 (nao divulgar).
    imp = (impacto or "").lower()
    if imp == "high":
        t = titulo.lower()
        return 5 if any(k in t for k in CINCO_ESTRELAS) else 4
    if imp == "medium":
        return 3
    return 0


def carregar_globais(hoje, janela_dias=7, log=print):
    fim = hoje + timedelta(days=janela_dias)
    agora = datetime.now(FUSO)
    vistos, saida = set(), []
    cab_http = {"User-Agent": "Mozilla/5.0 (L.I.C.A.)"}
    for url in FEEDS_GLOBAIS:
        nome = url.rsplit("/", 1)[-1]
        try:
            r = requests.get(url, timeout=20, headers=cab_http)
            r.raise_for_status()
            dados = r.json()
            log(f"[Calendario] {nome}: {len(dados)} eventos")
