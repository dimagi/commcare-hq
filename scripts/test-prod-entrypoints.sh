#!/bin/bash
set -e

echo "Testing gunicorn entrypoint"
python -c 'import deployment.gunicorn.commcarehq_wsgi'

echo "Testing celery entrypoint"
python -c 'import corehq.celery'
