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
            ev.append({"dia": d, "hora": "", "estrelas": n, "pais": pais, "titulo": titulo})

    for pais, nome, datas in BANCOS_CENTRAIS:
        if so_brasil and pais != "BRL":
            continue
        for d in datas:
            add(d, 5, pais, nome)
            if pais == "BRL":
                add(d + timedelta(days=6), 3, pais, "Ata do Copom (data estimada, confirme no BC)")
    add(proximo_dia_aproximado(hoje, 10), 4, "BRL", "IPCA (inflação) — data estimada, confirme no IBGE")
    if not so_brasil:
        add(proximo_dia_aproximado(hoje, 13), 4, "USD", "CPI dos EUA (inflação) — data estimada, confirme no BLS")
        p = primeira_sexta(hoje.year, hoje.month)
        if p < hoje:
            p = primeira_sexta(hoje.year + (hoje.month == 12), 1 if hoje.month == 12 else hoje.month + 1)
        add(p, 4, "USD", "Payroll dos EUA (empregos)")
    return ev


def montar_eventos(hoje, janela_dias=7, log=print):
    globais = carregar_globais(hoje, janela_dias, log)
    ev = globais + eventos_locais(hoje, janela_dias, so_brasil=bool(globais))
    return ev, bool(globais)


# ---------------- mensagem ----------------
def linhas_do_dia(evs):
    evs = sorted(evs, key=lambda e: (-e["estrelas"], e["hora"] or "99:99", e["pais"]))
    out = []
    for e in evs:
        hora = f"{e['hora']} " if e["hora"] else ""
        out.append(f"{'⭐' * e['estrelas']} {hora}{BANDEIRAS.get(e['pais'], '🌐')} {html.escape(e['titulo'])}")
    return out


def montar_mensagens(eventos, hoje, global_ok=True, limite=LIMITE_MSG):
    cab = (f"<b>📅 Calendário Econômico da Semana</b> — {hoje.strftime('%d/%m/%Y')}\n"
           "Eventos de 3 a 5 estrelas (⭐⭐⭐⭐⭐ = máximo impacto), horário de Brasília.")
    if not global_ok:
        cab += "\n⚠️ Fonte global indisponível: lista reduzida desta vez."
    rodape = "⚠️ Conteúdo informativo, não é recomendação de investimento."
    if not eventos:
        return [cab + "\n\nSem eventos relevantes previstos para os próximos 7 dias.\n\n" + rodape]

    por_dia = {}
    for e in eventos:
        por_dia.setdefault(e["dia"], []).append(e)

    blocos = []  # (cabecalho do dia, linhas)
    for d in sorted(por_dia):
        cd = f"<b>{DIAS[d.weekday()]}, {d.strftime('%d/%m')}</b>"
        blocos.append((cd, linhas_do_dia(por_dia[d])))

    msgs, atual = [], cab
    for cd, linhas in blocos:
        i, cont = 0, False
        while i < len(linhas):
            titulo = cd + (" (cont.)" if cont else "")
            trecho = [titulo]
            while i < len(linhas) and len("\n".join(trecho + [linhas[i]])) + 2 + len(atual) <= limite - len(rodape) - 4:
                trecho.append(linhas[i]); i += 1
            if len(trecho) == 1:  # nao coube nem uma linha: fecha a mensagem e recomeca
                if atual == "":
                    trecho.append(linhas[i]); i += 1
                else:
                    msgs.append(atual); atual = ""
                    continue
            atual = (atual + "\n\n" if atual else "") + "\n".join(trecho)
            cont = True
            if i < len(linhas):
                msgs.append(atual); atual = ""
    msgs.append(atual + "\n\n" + rodape)
    return msgs


def enviar_telegram(texto):
    url = f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendMessage"
    payload = {"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": texto, "parse_mode": "HTML",
               "disable_web_page_preview": "true"}
    resp = requests.post(url, data=payload, timeout=20)
    if resp.status_code != 200:
        raise RuntimeError(f"Telegram {resp.status_code}: {resp.text[:300]}")


def main():
    hoje = datetime.now(FUSO).date()
    eventos, global_ok = montar_eventos(hoje)
    msgs = montar_mensagens(eventos, hoje, global_ok)
    for m in msgs:
        enviar_telegram(m)
        print(m, "\n---")
    print(f"{len(msgs)} mensagem(ns) enviada(s); {len(eventos)} evento(s).")


if __name__ == "__main__":
    main()
