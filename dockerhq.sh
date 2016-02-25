#!/usr/bin/env bash

. $(dirname "$0")/docker/_include.sh
. $(dirname "$0")/docker/utils.sh

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

function nginx_runner() {
    sudo docker-compose -f $DOCKER_DIR/compose/docker-compose-nginx.yml -p commcarehq $@
}

function setup_production() {
    clear
    echo "Welcome to the CommCareHQ Docker production setup"
    ./create-kafka-topics.sh
    ./bootstrap.sh
    echo "CommcareHQ is ready to run in docker. "
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
    runserver-dev)
        ./docker/create-kafka-topics.sh
	web_runner run --name commcarehq_web_1 --rm --service-ports web /mnt/docker/runserver_dev.sh
        ;;
    runserver-prod)
        $DOCKER_DIR/docker-services.sh start
	web_runner run -d --name commcarehq_web_1 --rm --service-ports web /mnt/docker/runserver_prod.sh
        nginx_runner rm -f
        #wait for gunicorn web server in the web container to be up
        web_ip=$(get_container_ip "commcare.name" "web")
        while ! nc -z $web_ip 8000; do echo "Waiting for web container at $web_ip... "; sleep 3; done
        nginx_runner up -d
        ;;
    stopserver-prod)
        nginx_runner stop
        web_runner stop web
        docker rm -f commcarehq_web_1 #a bit of a hack due to a problem with docker-compose: https://github.com/docker/compose/issues/2593
        $DOCKER_DIR/docker-services.sh stop
        ;;
    proxy)
        nginx_runner $@
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
    setup-prod)
        ./docker/setup-prod.sh
        ;;
    bootstrap)
        $DOCKER_DIR/bootstrap.sh
        if [ "$?" -eq "0" ]; then
          web_runner up
        fi
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
