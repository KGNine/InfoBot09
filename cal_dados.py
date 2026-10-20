from datetime import date
from zoneinfo import ZoneInfo

FUSO = ZoneInfo("America/Sao_Paulo")
NY = ZoneInfo("America/New_York")
LIMITE_MSG = 3800  # Telegram aceita 4096

# Calendario global gratuito (Forex Factory / Fair Economy).
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

# Datas oficiais dos bancos centrais.
# Atualizar 1x por ano, quando cada banco publicar o calendario.
BANCOS_CENTRAIS = [
    ("BRL", "Decisão de juros do Copom (Selic)",
     [date(2026, 11, 4), date(2026, 12, 9)]),
    ("USD", "Decisão de juros do Fed (FOMC)",
     [date(2026, 10, 28), date(2026, 12, 9)]),
    ("EUR", "Decisão de juros do BCE",
     [date(2026, 10, 29), date(2026, 12, 17)]),
    ("GBP", "Decisão de juros do BoE",
     [date(2026, 11, 5), date(2026, 12, 17)]),
    ("JPY", "Decisão de juros do BoJ",
     [date(2026, 12, 17)]),
]
# FIM
