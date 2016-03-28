DOCKER_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

if [ `uname` == 'Linux' -o `uname` == 'Darwin' ]; then
    XDG_DATA_HOME=${XDG_DATA_HOME:-$HOME/.local/share}
    DOCKER_DATA_HOME=$XDG_DATA_HOME/dockerhq
else
    DOCKER_DATA_HOME=/data
fi

mkdir -p $DOCKER_DATA_HOME

XDG_CACHE_HOME=${XDG_CACHE_HOME:-$HOME/.cache}

PROJECT_NAME="commcarehq"

function web_runner() {
    if [ `uname` == 'Linux' ]; then
        sudo \
            env DOCKER_DATA_HOME=$DOCKER_DATA_HOME XDG_CACHE_HOME=$XDG_CACHE_HOME \
            docker-compose -f $DOCKER_DIR/compose/docker-compose-hq.yml -p $PROJECT_NAME $@
    else
        env DOCKER_DATA_HOME=$DOCKER_DATA_HOME XDG_CACHE_HOME=$XDG_CACHE_HOME \
            docker-compose -f $DOCKER_DIR/compose/docker-compose-hq.yml -p $PROJECT_NAME $@
    fi
}
