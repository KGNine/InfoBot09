from datetime import date, timedelta
from cal_dados import BANCOS_CENTRAIS
from cal_fontes import carregar_globais


def primeira_sexta(ano, mes):
    d = date(ano, mes, 1)
    while d.weekday() != 4:
        d += timedelta(days=1)
    return d


def proximo_mes(hoje):
    if hoje.month == 12:
        return hoje.year + 1, 1
    return hoje.year, hoje.month + 1


def proximo_dia(hoje, dia_alvo):
    candidato = date(hoje.year, hoje.month, dia_alvo)
    if candidato < hoje:
        ano, mes = proximo_mes(hoje)
        candidato = date(ano, mes, dia_alvo)
    return candidato


def eventos_locais(hoje, janela_dias=7, so_brasil=True):
    # Brasil (o calendario global nao cobre).
    # Se o global falhar, entram tambem os bancos centrais.
    limite = hoje + timedelta(days=janela_dias)
    ev = []

    def add(d, n, pais, titulo):
        if hoje <= d < limite:
            ev.append(dict(
                dia=d, hora="", estrelas=n, pais=pais, titulo=titulo,
            ))

    for pais, nome, datas in BANCOS_CENTRAIS:
        if so_brasil and pais != "BRL":
            continue
        for d in datas:
            add(d, 5, pais, nome)
            if pais == "BRL":
                add(d + timedelta(days=6), 3, pais,
                    "Ata do Copom (data estimada, confirme no BC)")
    add(proximo_dia(hoje, 10), 4, "BRL",
        "IPCA (inflação) — data estimada, confirme no IBGE")
    if not so_brasil:
        add(proximo_dia(hoje, 13), 4, "USD",
            "CPI dos EUA (inflação) — data estimada, confirme no BLS")
        p = primeira_sexta(hoje.year, hoje.month)
        if p < hoje:
            ano, mes = proximo_mes(hoje)
            p = primeira_sexta(ano, mes)
        add(p, 4, "USD", "Payroll dos EUA (empregos)")
    return ev


def montar_eventos(hoje, janela_dias=7, log=print):
    globais = carregar_globais(hoje, janela_dias, log)
    locais = eventos_locais(hoje, janela_dias, so_brasil=bool(globais))
    return globais + locais, bool(globais)
# FIM
