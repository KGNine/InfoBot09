import os
import re
import html
import requests
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

FUSO = ZoneInfo("America/Sao_Paulo")
NY = ZoneInfo("America/New_York")
LIMITE_MSG = 3800  # Telegram aceita 4096

# Calendario global gratuito (Forex Factory / Fair Economy): EUA, Zona do Euro, Japao, Australia,
# Reino Unido, Canada, Nova Zelandia, Suica e China. Nao cobre o Brasil (ver EVENTOS BR abaixo).
FEEDS_GLOBAIS = [
    "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
    "https://nfs.faireconomy.media/ff_calendar_nextweek.json",
]

BANDEIRAS = {"USD": "🇺🇸", "EUR": "🇪🇺", "JPY": "🇯🇵", "AUD": "🇦🇺", "GBP": "🇬🇧", "CAD": "🇨🇦",
             "NZD": "🇳🇿", "CHF": "🇨🇭", "CNY": "🇨🇳", "BRL": "🇧🇷", "ALL": "🌐"}
DIAS = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]

# Eventos que valem 5 estrelas quando o calendario os marca como alto impacto
CINCO_ESTRELAS = ["federal funds rate", "fomc statement", "main refinancing rate", "cash rate",
                  "boj policy rate", "policy rate", "official bank rate", "overnight rate",
                  "monetary policy", "non-farm", "cpi"]

# Traducao dos nomes mais comuns (o que nao estiver aqui aparece no original)
TRADUCOES = [
    (r"non-farm employment change", "Payroll (empregos fora do setor agrícola)"),
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
    """Calendario so tem 3 niveis. Mapeamento: alto = 4 (ou 5 se for juros, payroll ou CPI),
    medio = 3, baixo e feriado = 0 (nao divulgar)."""
    imp = (impacto or "").lower()
    if imp == "high":
        return 5 if any(k in titulo.lower() for k in CINCO_ESTRELAS) else 4
    if imp == "medium":
        return 3
    return 0


def carregar_globais(hoje, janela_dias=7, log=print):
    fim = hoje + timedelta(days=janela_dias)
    agora = datetime.now(FUSO)
    vistos, saida = set(), []
    for url in FEEDS_GLOBAIS:
        try:
            r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0 (L.I.C.A.)"})
            r.raise_for_status()
            dados = r.json()
            log(f"[Calendario] {url.rsplit('/', 1)[-1]}: {len(dados)} eventos")
        except Exception as e:
            log(f"[Calendario] feed falhou ({url.rsplit('/', 1)[-1]}): {e}")
            continue
        for e in dados:
            try:
                n = estrelas(e.get("impact"), e.get("title", ""))
                if n < 3:
                    continue
                dt = datetime.fromisoformat(e["date"])
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=NY)
                sem_hora = (dt.hour, dt.minute) == (0, 0)
                loc = dt.astimezone(FUSO)
                if not (hoje <= loc.date() < fim):
                    continue
                if not sem_hora and loc < agora:
                    continue  # evento que já aconteceu hoje não entra
                chave = (loc.isoformat(), e.get("country"), e.get("title"))
                if chave in vistos:
                    continue
                vistos.add(chave)
                saida.append({"dia": loc.date(), "hora": "" if sem_hora else loc.strftime("%H:%M"),
                              "estrelas": n, "pais": e.get("country", "ALL"),
                              "titulo": traduzir_titulo(e.get("title", ""))})
            except Exception as ex:
                log(f"[Calendario] evento ignorado: {ex}")
    return saida


# ---------------- EVENTOS BR (e plano B global) ----------------
# Datas oficiais confirmadas (atualizar 1x por ano, quando cada banco publicar o calendario do ano seguinte)
BANCOS_CENTRAIS = [
    ("BRL", "Decisão de juros do Copom (Selic)", [date(2026, 11, 4), date(2026, 12, 9)]),
    ("USD", "Decisão de juros do Fed (FOMC)", [date(2026, 10, 28), date(2026, 12, 9)]),
    ("EUR", "Decisão de juros do BCE", [date(2026, 10, 29), date(2026, 12, 17)]),
    ("GBP", "Decisão de juros do BoE", [date(2026, 11, 5), date(2026, 12, 17)]),
    ("JPY", "Decisão de juros do BoJ", [date(2026, 12, 17)]),
]


def primeira_sexta(ano, mes):
    d = date(ano, mes, 1)
    while d.weekday() != 4:
        d += timedelta(days=1)
    return d


def proximo_dia_aproximado(hoje, dia_alvo):
    candidato = date(hoje.year, hoje.month, dia_alvo)
    if candidato < hoje:
        candidato = date(hoje.year + (hoje.month == 12), 1 if hoje.month == 12 else hoje.month + 1, dia_alvo)
    return candidato


def eventos_locais(hoje, janela_dias=7, so_brasil=True):
    """Brasil (o calendario global nao cobre). Se o global falhar, entra tambem a lista dos bancos centrais."""
    limite = hoje + timedelta(days=janela_dias)
    ev = []

    def add(d, n, pais, titulo):
        if hoje <= d < limite:
            ev.append({"dia
