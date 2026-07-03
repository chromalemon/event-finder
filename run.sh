#!/usr/bin/env bash

set -e

source .venv/bin/activate

cd project

python -m uvicorn event_finder.asgi:application \
    --reload \
    --host 0.0.0.0 \
    --port 8000