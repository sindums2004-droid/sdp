FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5001 \
    DATABASE_PATH=/app/instance/management.db

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && addgroup --system app \
    && adduser --system --ingroup app app \
    && mkdir -p /app/instance \
    && chown -R app:app /app

COPY --chown=app:app app.py .
COPY --chown=app:app templates ./templates
COPY --chown=app:app static ./static

USER app

EXPOSE 5001

CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-5001} --workers 2 --access-logfile - --error-logfile - app:app"]
