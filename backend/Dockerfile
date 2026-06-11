FROM python:3.11-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.11-slim
RUN addgroup --system --gid 1001 app && \
    adduser --system --uid 1001 --gid 1001 app
WORKDIR /app
COPY --from=builder /usr/local /usr/local
COPY . .
RUN chown -R app:app /app && chmod +x /app/docker-entrypoint.sh
USER app
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --retries=5 --start-period=15s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1
ENTRYPOINT ["/app/docker-entrypoint.sh"]
