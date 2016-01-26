#!/bin/bash

set -e

if [ "$1" = 'help' ]; then
    echo "Pass any commands to this container to have them run by the container eg:"
    echo "  - python manage.py runserver 0.0.0.0:8000  # this is the default"
    echo "  - python manage.py shell"
    echo "  - python manage.py migrate"
    echo "  - bash"

    exit 0
fi

/mnt/docker/wait.sh

exec "$@"
