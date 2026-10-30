# Django + DRF + Channels backend. Build context: repository root.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY manage.py ./
COPY config config
COPY modules modules
RUN useradd --system app
USER app
EXPOSE 8000
# ponytail: migrate on boot is fine for one replica; move to a release job when running several
# ASGI (uvicorn) serves both HTTP and the /ws/display/ WebSocket.
CMD ["sh", "-c", "python manage.py migrate --noinput && uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --workers ${WEB_CONCURRENCY:-4} --proxy-headers --forwarded-allow-ips '*'"]
