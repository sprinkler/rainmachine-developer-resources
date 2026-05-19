#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage: $0 <name> <timezone> <latitude> <longitude> <elevation>"
    echo ""
    echo "  name       Device name (used as DB directory name, no commas)"
    echo "  timezone   IANA timezone string (e.g. Europe/Bucharest)"
    echo "  latitude   Decimal degrees (e.g. 47.1113296453)"
    echo "  longitude  Decimal degrees (e.g. 27.589685452)"
    echo "  elevation  Meters above sea level (e.g. 138.050109863)"
    echo ""
    echo "Example:"
    echo "  $0 RainMachine Europe/Bucharest 47.1113296453 27.589685452 138.050109863"
    exit 1
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
    usage
fi

if [ $# -ne 5 ]; then
    echo "Error: expected 5 arguments, got $#"
    echo ""
    usage
fi

NAME="$1"
TZ_STR="$2"
LAT="$3"
LON="$4"
ELEV="$5"

PARAMS="${NAME},${TZ_STR},${LAT},${LON},${ELEV}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SDK_DIR="${SCRIPT_DIR}/sdk-parsers"

echo "Starting RainMachine SDK in Docker..."
echo "  Params: ${PARAMS}"
echo "  DB will be created at: ${SDK_DIR}/DB/${NAME}/"
echo ""

docker run -it --rm \
    -v "${SDK_DIR}:/app" \
    -w /app \
    python:2.7 \
    python main.py "${PARAMS}"
