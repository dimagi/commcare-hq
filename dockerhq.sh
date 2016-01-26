#!/usr/bin/env bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
XDG_DATA_HOME=${XDG_DATA_HOME:-$HOME/.local/share}
DOCKER_DATA_HOME=$XDG_DATA_HOME/dockerhq

mkdir -p $DOCKER_DATA_HOME

XDG_CACHE_HOME=${XDG_CACHE_HOME:-$HOME/.cache}

PROJECT_NAME="commcarehq"

function usage() {
    case $1 in
        runserver)
            echo "Run the Django dev server"
            echo ""
            echo "runserver [OPTIONS]"
            echo "  -d  Run in background"
            ;;
        migrate)
            echo "Run the 'migrate' management command"
            echo ""
            echo "migrate [OPTIONS]"
            echo "  see Django migrate docs for options"
            ;;
        shell)
            echo "Run the Django shell"
            echo ""
            ;;
        rebiuld)
            echo "Rebuild the 'web' image"
            echo ""
            ;;
        bash)
            echo "Run the bash shell"
            echo ""
            ;;
        services)
            echo "Run service commands"
            echo ""
            $DIR/docker/docker-services.sh --help
            ;;
        *)
            echo "Helper script to start and stop services for CommCare HQ"
            echo ""
            echo "./dockerhq.sh [OPTIONS] COMMAND"
            echo "      -h --help"
            echo "      runserver|migrate|shell|bash|rebuild|bootstrap|services"
            echo ""
            echo "./dockerhq.sh help COMMAND"
            ;;
    esac
    exit
}

function runner() {
    sudo \
        env DOCKER_DATA_HOME=$DOCKER_DATA_HOME XDG_CACHE_HOME=$XDG_CACHE_HOME\
        docker-compose -f $DIR/docker/docker-compose-web.yml -p $PROJECT_NAME $@
}

key="$1"
shift

case $key in
    -h | --help | help)
        usage $@
        ;;
    services)
        $DIR/docker/docker-services.sh $@
        ;;
    migrate)
        runner run web python manage.py migrate $@
        ;;
    runserver)
        runner up $@
        ;;
    shell)
        runner run web python manage.py shell
        ;;
    bash)
        runner run web bash
        ;;
    rebuild)
        $DIR/docker/docker-services.sh down
        runner down
        runner build
        ;;
    bootstrap)
        $DIR/docker/bootstrap.sh
        ;;
    ps)
        runner ps
        $DIR/docker/docker-services.sh ps
        ;;
    *)
        runner $key $@
        ;;
esac
exit
