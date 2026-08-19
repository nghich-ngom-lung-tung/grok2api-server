#!/bin/sh
set -e

quality_guard_dir=/var/lib/grok2api-quality-guard
mkdir -p "${quality_guard_dir}" /app/data /run/grok2api
chown -R grok2api:grok2api "${quality_guard_dir}" /app/data /run/grok2api
chmod 0700 "${quality_guard_dir}"

CONFIG_FILE="/app/config.yaml"

if [ -n "${GROK2API_CONFIG_SOURCE:-}" ] && [ -f "${GROK2API_CONFIG_SOURCE}" ]; then
  cp "${GROK2API_CONFIG_SOURCE}" /app/config.yaml
elif [ ! -f "/app/config.yaml" ]; then
  if [ -f "/app/config.default.yaml" ]; then
    cp "/app/config.default.yaml" /app/config.yaml
  fi
fi

if [ -f "/app/config.yaml" ]; then
  chown grok2api:grok2api /app/config.yaml
  chmod 0600 /app/config.yaml
fi

# Render dynamically sets PORT env var
PORT="${PORT:-8000}"

echo "Starting grok2api on 0.0.0.0:${PORT}..."
exec su-exec grok2api:grok2api /app/grok2api --config /app/config.yaml --listen "0.0.0.0:${PORT}"
