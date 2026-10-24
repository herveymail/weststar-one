# Weststar ONE — production image. Non-root, no compilers in the final image.
FROM python:3.13-slim-bookworm AS build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential pkg-config default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /tmp/
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r /tmp/requirements.txt

FROM python:3.13-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MEDIA_ROOT=/data/media
RUN apt-get update && apt-get install -y --no-install-recommends libmariadb3 tini \
    libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-dejavu-core fonts-liberation2 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 10001 --home /app weststar \
    && mkdir -p /data/media && chown weststar:weststar /data/media
COPY --from=build /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels
WORKDIR /app
COPY --chown=root:root . /app
# Static files are built into the image (served by whitenoise). Dummy keys only for this build step.
RUN SECRET_KEY=build-only-not-used-at-runtime-000000000000000 APP_ENCRYPTION_KEY=$(python -c "import base64;print(base64.b64encode(b'0'*32).decode())") \
    DB_PASSWORD=x python manage.py collectstatic --noinput -v0 \
    && chmod -R a+rX,go-w /app && chmod +x deploy/entrypoint.sh
USER weststar
EXPOSE 8000
ENTRYPOINT ["/usr/bin/tini", "--", "/app/deploy/entrypoint.sh"]
CMD ["web"]
HEALTHCHECK --interval=10s --timeout=5s --start-period=120s --retries=6 CMD python -c "import os,urllib.request,urllib.parse;h=urllib.parse.urlparse(os.environ['APP_URL']).hostname;urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8000/health/',headers={'Host':h}),timeout=4)" || exit 1
