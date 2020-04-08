#!/usr/bin/env bash

#############################################
set -e; cd "$(dirname "$0")" # Script Start #
#############################################

COURATOR_HOST=${COURATOR_HOST:-0.0.0.0}
COURATOR_PORT=${COURATOR_PORT:-8001}

source .venv/bin/activate
gunicorn -b "$COURATOR_HOST:$COURATOR_PORT" "$@" courator:app

