import os
import requests

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def buscar_novos_membros():
    resp = requests.get(f"{BASE_URL}/getUpdates", timeout=15)
    resp.raise_for_status()
    updates = resp.json().get("result", [])

    nomes = []
    max_update_id = None

    for update in updates:
        max_update_id = update["update_id"]
        msg = update.get("message", {})
        for membro in msg.get("new_chat_members", []):
            if not membro.get("is_bot"):
                nomes.append(membro.get("first_name", "novo membro"))

    # Confirma o processamento — limpa a fila do lado do Telegram, evitando repetir
    if max_update_id is not None:
        requests.get(f"{BASE_URL}/getUpdates", params={"offset": max_update_id + 1}, timeout=15)

    return nomes


def montar_boas_vindas(nomes):
    if len(nomes) == 1:
        saudacao = f"👋 Seja bem-vindo(a), *{nomes[0]}*!"
    else:
        saudacao = f"👋 Seja bem-vindos, *{', '.join(nomes)}*!"

    return (
        f"{saudacao}\n\n"
        "Você acaba de entrar no *L.I.C.A.* — informação financeira automatizada, "
        "direto ao ponto, sem enrolação.\n\n"
        "Aqui você vai encontrar:\n"
        "🪙 Cripto Pulse • 🇧🇷 Termômetro BR • 🌍 Giro Global\n"
        "📈 Sala de Trade • 🤖 Radar IA • 🌦️ Clima & Mercado\n\n"
        "Fique à vontade pra explorar o histórico de mensagens fixadas. "
        "Bons investimentos! 📊"
    )


def enviar_telegram(texto):
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": texto, "parse_mode": "Markdown"}
    resp = requests.post(f"{BASE_URL}/sendMessage", data=payload, timeout=15)
    resp.raise_for_status()


def main():
    nomes = buscar_novos_membros()
    if not nomes:
        print("Nenhum membro novo desde a última checagem.")
        return

    mensagem = montar_boas_vindas(nomes)
    enviar_telegram(mensagem)
    print("Boas-vindas enviadas para:", nomes)


if __name__ == "__main__":
    main()
