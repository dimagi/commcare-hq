#!/usr/bin/env bash

. $(dirname "$0")/docker/_include.sh

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
        rebuild)
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

key="$1"
shift

case $key in
    -h | --help | help)
        usage $@
        ;;
    services)
        $DOCKER_DIR/docker-services.sh $@
        ;;
    migrate)
        web_runner run web python manage.py migrate $@
        ;;
    runserver)
        web_runner up $@
        ;;
    shell)
        web_runner run web python manage.py shell
        ;;
    bash)
        web_runner run web bash
        ;;
    rebuild)
        $DOCKER_DIR/docker-services.sh down
        web_runner down
        web_runner build
        ;;
    bootstrap)
        $DOCKER_DIR/bootstrap.sh
        ;;
    ps)
        web_runner ps
        $DOCKER_DIR/docker-services.sh ps
        ;;
    *)
        web_runner $key $@
        ;;
esac
exit
