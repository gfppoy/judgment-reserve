FROM node:22-bookworm-slim AS node
FROM python:3.12-slim-bookworm
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir numpy==2.3.5 \
    && npm install -g @openai/codex@0.166.0 @anthropic-ai/claude-code@2.1.295 \
    && useradd -m -u 1000 researcher
COPY entrypoint.py egress_proxy.py claude-settings.json /opt/reserve/
ENV HOME=/home/researcher PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
WORKDIR /workspace
USER researcher
ENTRYPOINT ["python", "/opt/reserve/entrypoint.py"]
