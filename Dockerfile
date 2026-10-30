# Development environment: Python 3.11 on Debian
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CHROME_BIN=/usr/bin/chromium \
    CHROMEDRIVER=/usr/bin/chromedriver

# Chrome browser + matching Chrome driver
RUN apt-get update && apt-get install -y --no-install-recommends \
        chromium \
        chromium-driver \
        fonts-liberation \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Selenium automation code, summarizer, and API server
COPY . .

EXPOSE 7000

# API starts automatically when the container runs
CMD ["gunicorn", "--workers", "1", "--threads", "4", "--timeout", "180", \
     "--bind", "0.0.0.0:7000", "app:app"]