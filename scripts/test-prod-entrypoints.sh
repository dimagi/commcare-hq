#!/bin/bash
set -e

echo "Testing gunciron entrypoint"
python -c 'import deployment.gunicorn.commcarehq_wsgi'

echo "Testing websockets entrypoint"
uwsgi --http-socket web.socket --test deployment.websocket_wsgi

echo "Testing celery entrypoint"
python -c 'import corehq.celery'
