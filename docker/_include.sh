DOCKER_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
XDG_DATA_HOME=${XDG_DATA_HOME:-$HOME/.local/share}
UDO=""

if [ "$DOCKER_BETA" == "true" ]; then
    DOCKER_DATA_HOME=$XDG_DATA_HOME/dockerhq
elif [ `uname` == 'Linux' ]; then
    DOCKER_DATA_HOME=$XDG_DATA_HOME/dockerhq
    UDO="sudo"
else
    DOCKER_DATA_HOME=/data
fi

if [ `uname` == 'Darwin' -a "$DOCKER_BETA" != "true" ]; then
    docker-machine ssh $DOCKER_MACHINE_NAME sudo mkdir -p $DOCKER_DATA_HOME
else
    mkdir -p $DOCKER_DATA_HOME
fi

XDG_CACHE_HOME=${XDG_CACHE_HOME:-$HOME/.cache}

PROJECT_NAME="commcarehq"

function web_runner() {
    $UDO \
        env DOCKER_DATA_HOME=$DOCKER_DATA_HOME XDG_CACHE_HOME=$XDG_CACHE_HOME \
        docker-compose -f $DOCKER_DIR/compose/docker-compose-hq.yml -p $PROJECT_NAME $@
}
