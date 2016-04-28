DOCKER_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

if [ `uname` == 'Linux' ]; then
    XDG_DATA_HOME=${XDG_DATA_HOME:-$HOME/.local/share}
    DOCKER_DATA_HOME=$XDG_DATA_HOME/dockerhq
    UDO="sudo"
else
    DOCKER_DATA_HOME=/data
    UDO=""
fi

if [ `uname` == 'Darwin' ]; then
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
