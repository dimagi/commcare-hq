#!/usr/bin/env bash

. $(dirname "$0")/docker/_include.sh
. $(dirname "$0")/docker/utils.sh

function usage() {
    case $1 in
        runserver-dev)
            echo "Run the Django dev server"
            echo ""
            echo "runserver-dev [OPTIONS]"
            echo "  -d  Run in background"
            ;;
        runserver-prod)
            echo "Run the whole setup in production mode. Forwards to port 80."
            echo "Make sure to run ./dockerhq.sh setup-prod first time before this command. "
            ;;
        stopserver)
            echo "Stops the production setup."
            echo ""
            ;;
        setup-prod)
            echo "Sets up static files, kafka topics etc. for the first production run."
            echo ""
            ;;
        migrate)
            echo "Run the 'migrate' management command"
            echo ""
            echo "migrate [OPTIONS]"
            echo "  see Django migrate docs for options"
            ;;
        proxy)
            echo "Start the Nginx proxy. "
            echo "-d to run in background"
            echo "./dockerhq.sh proxy [-d] up|stop"
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
            echo "      runserver-dev|runserver-prod|stopserver-prod|setup-prod|proxy|migrate|shell|bash|rebuild|bootstrap|services"
            echo ""
            echo "Requires docker-compose v. >1.7.0 and netcat installed. "
            echo ""
            echo "To get up and running run first time: "
            echo "./dockerhq.sh bootstrap"
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
        web_runner run --rm -e CUSTOMSETTINGS="docker.localsettings_docker" --service-ports web python manage.py migrate $@
        ;;
    runserver-dev)
	web_runner run --name commcarehq_web_1 --rm --service-ports web /mnt/docker/runserver_dev.sh
        ;;
    runserver-prod)
        docker rm hqservice_kafka_1
	$DOCKER_DIR/docker-services.sh start
	web_runner run --name commcarehq_web_1 -d --rm web /mnt/docker/runserver_prod.sh $@
        nginx_runner rm -f
        #wait for gunicorn web server in the web container to be up
        web_ip=$(get_container_ip "commcare.name" "web")
        while ! nc -z $web_ip 8000; do echo "Waiting for web container at $web_ip... "; sleep 3; done
        nginx_runner up -d
        ;;
    stopserver)
        nginx_runner stop
        web_runner stop web
        docker rm -f commcarehq_web_1 #a bit of a hack due to a problem with docker-compose: https://github.com/docker/compose/issues/2593
        $DOCKER_DIR/docker-services.sh stop
        ;;
    setup-prod)
        $DOCKER_DIR/docker-services.sh start
        ./docker/create-kafka-topics.sh
        web_runner run --name commcarehq_web_1 --rm --service-ports web /mnt/docker/setup-prod.sh
        ;;
    proxy)
        nginx_runner $@
        ;;
    shell)
        web_runner run --rm web python manage.py shell
        ;;
    bash)
        web_runner run --rm -e CUSTOMSETTINGS="docker.localsettings_docker" --service-ports web bash
        ;;
    rebuild)
        rebuild
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
