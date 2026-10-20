import html
from cal_dados import BANDEIRAS, DIAS, LIMITE_MSG


def linhas_do_dia(evs):
    evs = sorted(
        evs,
        key=lambda e: (-e["estrelas"], e["hora"] or "99:99", e["pais"]),
    )
    out = []
    for e in evs:
        hora = f"{e['hora']} " if e["hora"] else ""
        bandeira = BANDEIRAS.get(e["pais"], "🌐")
        titulo = html.escape(e["titulo"])
        estr = "⭐" * e["estrelas"]
        out.append(f"{estr} {hora}{bandeira} {titulo}")
    return out


def cabecalho(hoje, global_ok):
    cab = (
        f"<b>📅 Calendário Econômico da Semana</b> — "
        f"{hoje.strftime('%d/%m/%Y')}\n"
        "Eventos de 3 a 5 estrelas (⭐⭐⭐⭐⭐ = máximo impacto), "
        "horário de Brasília."
    )
    if not global_ok:
        cab += "\n⚠️ Fonte global indisponível: lista reduzida desta vez."
    return cab


def montar_mensagens(eventos, hoje, global_ok=True, limite=LIMITE_MSG):
    cab = cabecalho(hoje, global_ok)
    rodape = "⚠️ Conteúdo informativo, não é recomendação de investimento."
    if not eventos:
        vazio = "Sem eventos relevantes previstos para os próximos 7 dias."
        return [cab + "\n\n" + vazio + "\n\n" + rodape]

    por_dia = {}
    for e in eventos:
        por_dia.setdefault(e["dia"], []).append(e)

    blocos = []  # (cabecalho do dia, linhas)
    for d in sorted(por_dia):
        cd = f"<b>{DIAS[d.weekday()]}, {d.strftime('%d/%m')}</b>"
        blocos.append((cd, linhas_do_dia(por_dia[d])))

    ate = limite - len(rodape) - 4
    msgs, atual = [], cab
    for cd, linhas in blocos:
        i, cont = 0, False
        while i < len(linhas):
            titulo = cd + (" (cont.)" if cont else "")
            trecho = [titulo]
            while i < len(linhas):
                prox = "\n".join(trecho + [linhas[i]])
                if len(prox) + 2 + len(atual) > ate:
                    break
                trecho.append(linhas[i])
                i += 1
            if len(trecho) == 1:
                # nao coube nem uma linha: fecha a mensagem e recomeca
                if atual == "":
                    trecho.append(linhas[i])
                    i += 1
                else:
                    msgs.append(atual)
                    atual = ""
                    continue
            atual = (atual + "\n\n" if atual else "") + "\n".join(trecho)
            cont = True
            if i < len(linhas):
                msgs.append(atual)
                atual = ""
    msgs.append(atual + "\n\n" + rodape)
    return msgs
# FIM
