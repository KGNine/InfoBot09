import os
import requests
from datetime import datetime
from cal_dados import FUSO
from cal_local import montar_eventos
from cal_msg import montar_mensagens


def enviar_telegram(texto):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": os.environ["TELEGRAM_CHAT_ID"],
        "text": texto,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }
    resp = requests.post(url, data=payload, timeout=20)
    print("Telegram status:", resp.status_code)
    dados = resp.json()
    if resp.status_code != 200 or not dados.get("ok"):
        raise RuntimeError(f"Telegram {resp.status_code}: {resp.text[:300]}")
    chat = dados["result"]["chat"]
    print("Enviado para:", chat.get("title"), chat.get("id"))


def main():
    hoje = datetime.now(FUSO).date()
    eventos, global_ok = montar_eventos(hoje)
    msgs = montar_mensagens(eventos, hoje, global_ok)
    for m in msgs:
        enviar_telegram(m)
        print(m, "\n---")
    print(f"{len(msgs)} mensagem(ns) enviada(s); "
          f"{len(eventos)} evento(s).")


if __name__ == "__main__":
    main()
# FIM
