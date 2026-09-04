# POLY 2026-08-31 (UTC) — estado de bots
- poly-elon:       active   (bot-polymarket-elon, 48h)
- poly-semanal:    active   (bot-polymarket-elon-semanal)
- poly-mensual:    active   (bot-polymarket-elon-mensual)
- poly-zelenskyy:  active   (bot-polymarket-zelenskyy)
- poly-telegram:   active   (bot de comandos de Elon)
- poly-trump:      active   (bot-polymarket-trump, semanal Truth Social)

Último check de salud: 2026-08-31. Todos los bots en estado OK según
check_salud.py / check_integral.py (corre cada 15 min en cron).

Fuente de datos de Trump: xtracker.polymarket.com (Truth Social) +
jina.ai como respaldo + nitter como último recurso (ver
bot-polymarket-trump/recoger_tweets.py).

Mercados activos de Trump (3 semanales, gamma-api):
- "Donald Trump # Truth Social Weekly Count – Week of <fecha>"

CSV de datos histórico: bot-polymarket-trump/datos_trump.csv

