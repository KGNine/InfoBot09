import re
import requests
from datetime import datetime, timedelta
from cal_dados import FUSO, NY, FEEDS_GLOBAIS, CINCO_ESTRELAS
from cal_traducoes import TRADUCOES


def traduzir_titulo(t):
    out = t
    for padrao, pt in TRADUCOES:
        out = re.sub(padrao, pt, out, flags=re.I)
    return out


def estrelas(impacto, titulo):
    # alto = 4 (5 se for juros, payroll ou CPI), medio = 3,
    # baixo e feriado = 0 (nao divulgar).
    imp = (impacto or "").lower()
    if imp == "high":
        t = titulo.lower()
        return 5 if any(k in t for k in CINCO_ESTRELAS) else 4
    if imp == "medium":
        return 3
    return 0


def baixar(url, log):
    nome = url.rsplit("/", 1)[-1]
    cab_http = {"User-Agent": "Mozilla/5.0 (L.I.C.A.)"}
    try:
        r = requests.get(url, timeout=20, headers=cab_http)
        r.raise_for_status()
        dados = r.json()
    except Exception as e:
        log(f"[Calendario] feed falhou ({nome}): {e}")
        return []
    log(f"[Calendario] {nome}: {len(dados)} eventos")
    return dados


def converter(e, hoje, fim, agora):
    n = estrelas(e.get("impact"), e.get("title", ""))
    if n < 3:
        return None
    dt = datetime.fromisoformat(e["date"])
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=NY)
    sem_hora = (dt.hour, dt.minute) == (0, 0)
    loc = dt.astimezone(FUSO)
    if not (hoje <= loc.date() < fim):
        return None
    if not sem_hora and loc < agora:
        return None  # evento que ja aconteceu hoje nao entra
    hora = "" if sem_hora else loc.strftime("%H:%M")
    return dict(
        dia=loc.date(), hora=hora, estrelas=n,
        pais=e.get("country", "ALL"),
        titulo=traduzir_titulo(e.get("title", "")),
    )


def carregar_globais(hoje, janela_dias=7, log=print):
    fim = hoje + timedelta(days=janela_dias)
    agora = datetime.now(FUSO)
    vistos, saida = set(), []
    for url in FEEDS_GLOBAIS:
        for e in baixar(url, log):
            try:
                ev = converter(e, hoje, fim, agora)
            except Exception as ex:
                log(f"[Calendario] evento ignorado: {ex}")
                continue
            if ev is None:
                continue
            chave = (ev["dia"], ev["hora"], ev["pais"], ev["titulo"])
            if chave in vistos:
                continue
            vistos.add(chave)
            saida.append(ev)
    return saida
# FIM
