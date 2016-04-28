#!/usr/bin/env bash

while ! nc -z rabbit 5672; do echo "Waiting for RabbitMQ... \n"; sleep 3; done
python manage.py celery flower --address=0.0.0.0 --port=5555 --broker='amqp://guest:guest@rabbit:5672/commcarehq' &
python manage.py celery worker --queues=beat,background_queue,celery,saved_exports_queue,celery_periodic,ucr_queue,reminder_rule_queue,email_queue,logistics_background_queue --broker='amqp://guest:guest@rabbit:5672/commcarehq'

