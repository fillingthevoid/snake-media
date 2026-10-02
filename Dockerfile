FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    TZ=America/Los_Angeles

WORKDIR /app
RUN groupadd --gid 10001 snake-media \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin snake-media
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY --chmod=0755 src/ ./src/
USER 10001:10001
CMD ["python", "-m", "snake_media"]
