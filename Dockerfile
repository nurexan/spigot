FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    BOT_TOKEN="8751576357:AAHVuGYC8Ua3WnSKeRKI64oXRe7o6mM0_Ck" \
    ADMIN_IDS="7832781255"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "bot.py"]
