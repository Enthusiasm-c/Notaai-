# ────────────────────── 1-я стадия: builder ──────────────────────
FROM python:3.11-slim AS builder
WORKDIR /app

# Обновляем APT и ставим gcc + curl только здесь
RUN set -eux \
 && apt-get update \
 && apt-get install -y --no-install-recommends build-essential curl \
 && rm -rf /var/lib/apt/lists/*

# Кэшируем python-зависимости в виде wheel-ов
COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip wheel -r requirements.txt -w /wheels

# ────────────────────── 2-я стадия: runtime ──────────────────────
FROM python:3.11-slim
WORKDIR /app

# — В runtime-слое APT больше не нужен —
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* \
 && rm -rf /wheels

# Копируем исходный код бота
COPY . /app

# Удобный вывод в логах
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

CMD ["python", "main.py"]
