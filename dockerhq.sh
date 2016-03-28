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

function rebuild() {
    web_runner down
    web_runner build
}

function travis_runner() {
    sudo docker-compose -f $DOCKER_DIR/compose/docker-compose-travis.yml -p travis $@
}

function travis_js_runner() {
    sudo docker-compose -f $DOCKER_DIR/compose/docker-compose-travis-js.yml -p travis $@
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
    travis)
        travis_runner $@
        ;;
    travis-js)
        travis_js_runner $@
        ;;
    migrate)
        web_runner run --rm web python manage.py migrate $@
        ;;
    runserver)
        web_runner run --service-ports web $@
        ;;
    shell)
        web_runner run --rm web python manage.py shell
        ;;
    bash)
        web_runner run --rm --service-ports web bash
        ;;
    rebuild)
        rebuild
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
