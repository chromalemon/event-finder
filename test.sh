#!/usr/bin/env bash

set -e

docker compose run --rm web python manage.py test
