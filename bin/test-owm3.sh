#!/usr/bin/env bash
set -euo pipefail
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
docker run --rm \
    --env-file "${REPO_DIR}/.env" \
    -e PYTHONPATH=/app \
    -v "${REPO_DIR}/sdk-parsers:/app" \
    -w /app \
    python:2.7 \
    python RMParserFramework/parsers/owm3-parser.py
