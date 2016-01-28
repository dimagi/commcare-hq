TRAVIS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

setup_elasticsearch() {
    es_version=0.90.13

    echo "Installing elasticsearch version ${es_version}"

    wget "https://download.elastic.co/elasticsearch/elasticsearch/elasticsearch-${es_version}.tar.gz" -O elasticsearch.tar.gz

    tar xvzf elasticsearch.tar.gz
    nohup bash -c "cd elasticsearch-${es_version} && bin/elasticsearch &"
    sleep 10
}

setup_kafka() {
    # kafka install, copied from https://github.com/wvanbergen/kafka/blob/master/.travis.yml
    wget http://www.us.apache.org/dist/kafka/0.8.2.1/kafka_2.10-0.8.2.1.tgz -O kafka.tgz
    mkdir -p kafka && tar xzf kafka.tgz -C kafka --strip-components 1
    nohup bash -c "cd kafka && bin/zookeeper-server-start.sh config/zookeeper.properties &"
    nohup bash -c "cd kafka && bin/kafka-server-start.sh config/server.properties &"
    sleep 10
    kafka/bin/kafka-topics.sh --create --partitions 1 --replication-factor 1 --topic case --zookeeper localhost:2181
    kafka/bin/kafka-topics.sh --create --partitions 1 --replication-factor 1 --topic form --zookeeper localhost:2181
    kafka/bin/kafka-topics.sh --create --partitions 1 --replication-factor 1 --topic meta --zookeeper localhost:2181
    kafka/bin/kafka-topics.sh --create --partitions 1 --replication-factor 1 --topic case-sql --zookeeper localhost:2181
    kafka/bin/kafka-topics.sh --create --partitions 1 --replication-factor 1 --topic form-sql --zookeeper localhost:2181
}

create_topics() {
    topics_script=$1
    zookeeper_ip=$2
    topics=$3

    for topic in $topics; do
        $TRAVIS_DIR/../dockerhq.sh travis run --rm kafka $topics_script --create --partitions 1 --replication-factor 1 --zookeeper $zookeeper_ip:2181 --topic $topic
    done
}

setup_kafka_docker() {
    kafka_topics=$(./dockerhq.sh travis run --rm kafka find /opt -name kafka-topics.sh | tr -d '\n' | tr -d '\r')
    CID=$(sudo docker ps -fq ancestor=spotify/kafka -f status=running)
    zookeeper_ip=$(sudo docker inspect --format '{{ .NetworkSettings.IPAddress }}' ${CID} | tr -d '\n' | tr -d '\r')
    echo $zookeeper_ip
    create_topics $kafka_topics $zookeeper_ip "case form meta case-sql form-sql"
}

setup_moto_s3_server() {
    mkdir -p moto-s3 && cd moto-s3
    test -d env || virtualenv env
    # todo: switch to https://github.com/spulec/moto.git when PR is merged
    # https://github.com/spulec/moto/pull/518
    test -d moto || git clone https://github.com/dimagi/moto.git
    env/bin/pip install -e ./moto
    env/bin/moto_server -H localhost -p 5000 s3 &
    cd ..
}
