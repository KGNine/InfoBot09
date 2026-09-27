import os
import requests
from datetime import date, timedelta

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# Datas oficiais confirmadas (atualizar uma vez por ano)
COPOM_2026 = [date(2026, 11, 4), date(2026, 12, 9)]
FOMC_2026 = [date(2026, 10, 28), date(2026, 12, 9)]


def primeira_sexta(ano, mes):
    d = date(ano, mes, 1)
    while d.weekday() != 4:
        d += timedelta(days=1)
    return d


def proximo_dia_aproximado(hoje, dia_alvo):
    candidato = date(hoje.year, hoje.month, dia_alvo)
    if candidato < hoje:
        if hoje.month == 12:
            candidato = date(hoje.year + 1, 1, dia_alvo)
        else:
            candidato = date(hoje.year, hoje.month + 1, dia_alvo)
    return candidato


def montar_eventos(hoje, janela_dias=7):
    limite = hoje + timedelta(days=janela_dias)
    eventos = []

    for d in COPOM_2026:
        if hoje <= d <= limite:
            eventos.append((d, 5, "🇧🇷 Decisão do Copom (Selic)"))

    for d in FOMC_2026:
        if hoje <= d <= limite:
            eventos.append((d, 5, "🌍 Decisão do FOMC (juros EUA)"))

    ipca = proximo_dia_aproximado(hoje, 10)
    if hoje <= ipca <= limite:
        eventos.append((ipca, 4, "🇧🇷 IPCA (inflação) — data estimada, confirme no IBGE"))

    cpi = proximo_dia_aproximado(hoje, 13)
    if hoje <= cpi <= limite:
        eventos.append((cpi, 4, "🌍 CPI dos EUA (inflação) — data estimada, confirme no BLS"))

    payroll = primeira_sexta(hoje.year, hoje.month)
    if payroll < hoje:
        prox_mes = hoje.month + 1 if hoje.month < 12 else 1
        prox_ano = hoje.year if hoje.month < 12 else hoje.year + 1
        payroll = primeira_sexta(prox_ano, prox_mes)
    if hoje <= payroll <= limite:
        eventos.append((payroll, 4, "🌍 Payroll dos EUA (empregos)"))

    # Ordena por importância (mais estrelas primeiro), depois por data
    eventos.sort(key=lambda x: (-x[1], x[0]))
    return eventos


def montar_mensagem():
    hoje = date.today()
    eventos = montar_eventos(hoje)

    linhas = [f"*📅 Calendário Econômico da Semana* — {hoje.strftime('%d/%m/%Y')}", ""]
    if not eventos:
        linhas.append("Sem eventos relevantes previstos para os próximos 7 dias.")
    else:
        for d, estrelas, nome in eventos:
            estrelas_txt = "⭐" * estrelas
            linhas.append(f"{estrelas_txt} — {d.strftime('%d/%m')} — {nome}")

    return "\n".join(linhas)


def enviar_telegram(texto):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": texto, "parse_mode": "Markdown"}
    resp = requests.post(url, data=payload, timeout=15)
    resp.raise_for_status()


def main():
    mensagem = montar_mensagem()
    enviar_telegram(mensagem)
    print("Mensagem enviada com sucesso:")
    print(mensagem)


if __name__ == "__main__":
    main()
