name: "Conteudo gratuito no Telegram"

on: {
  "schedule": [
    {"cron": "12 10,12,14,16,18,20 * * *"}
  ],
  "workflow_dispatch": {
    "inputs": {
      "pilar": {
        "description": "Indice do pilar para testar (0 a 5). Deixe vazio para automatico.",
        "required": false,
        "default": ""
      }
    }
  }
}

jobs: {
  "enviar-conteudo": {
    "runs-on": "ubuntu-latest",
    "steps": [
      {"name": "Checkout do repositorio", "uses": "actions/checkout@v4"},
      {"name": "Configurar Python", "uses": "actions/setup-python@v5", "with": {"python-version": "3.11"}},
      {"name": "Instalar dependencias", "run": "pip install -r requirements.txt"},
      {
        "name": "Rodar script",
        "env": {
          "TELEGRAM_BOT_TOKEN": "${{ secrets.TELEGRAM_BOT_TOKEN }}",
          "TELEGRAM_CHAT_ID": "${{ secrets.TELEGRAM_CHAT_ID }}"
        },
        "run": "python content_free.py"
      }
    ]
  }
}
