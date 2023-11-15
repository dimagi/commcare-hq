#!/usr/bin/env bash

if [ -z "$SUDO_USER" ]; then
    echo "This script is intended to be run as sudo. Exiting"
    exit 1
fi

run_segment() {
    case "$1" in
    1) dependencies ;;
    2) pyenv ;;
    3) frontend ;;
    4) containers ;;
    5) databases ;;
    *) echo "Invalid number $1";;
    esac
}

MAX_STEPS=5

run_setup () {
    START="$1"; shift
    [ -z "$START" ] && START=1

    CONTAINER="$1";  shift
    [ -z "$CONTAINER" ] && CONTAINER="$(< .setup_container)"
    CONTAINER="${CONTAINER:-podman}"
    echo "$CONTAINER" > .setup_container

    for i in $(seq "$START" "$MAX_STEPS"); do
        echo $i > .setup_progress
        run_segment $i
    done

    rm  .setup_progress
    rm  .setup_container

    echo "Installation and setup complete"
    echo "Please open a new terminal to access the updated environment"
    echo "You can then run the server with './manage.py runserver 0.0.0.0:8000'"
}

dependencies () {
    echo "setting up dependencies"
    setup/dependencies.sh
}

pyenv () {
    echo "setting up pyenv"
    sudo -u $SUDO_USER setup/pyenv.sh
}

frontend () {
    echo "setting up frontend"
    sudo -u $SUDO_USER setup/frontend.sh
}

containers () {
    CONTAINER=$(< .setup_container)
    if [[ "$CONTAINER" == "podman" ]]; then
        echo "setting up podman"
        setup/podman.sh
    else
        echo "setting up docker"
        setup/docker.sh
    fi
}

databases () {
    echo "setting up databases"
    sudo -u $SUDO_USER setup/database.sh
}

touch .setup_progress
touch .setup_container
run_setup "$(< .setup_progress)" $@
