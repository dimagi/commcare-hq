DOWNLOAD_DIR=${HOME}/downloads

setup_elasticsearch() {
    es_version=0.90.13
    es_dir=${DOWNLOAD_DIR}/elasticsearch-${es_version}

    echo "Installing elasticsearch version ${es_version}"

    if [ ! -d ${es_dir } ]; then
        wget "https://download.elastic.co/elasticsearch/elasticsearch/elasticsearch-${es_version}.tar.gz" -O ${DOWNLOAD_DIR}/elasticsearch.tar.gz

        tar xvzf ${DOWNLOAD_DIR}/elasticsearch.tar.gz
    fi

    nohup bash -c "cd ${es_dir} && bin/elasticsearch &"
    sleep 5
}

setup_kafka() {
    kafka_dir=${DOWNLOAD_DIR}/kafka
    # kafka install, copied from https://github.com/wvanbergen/kafka/blob/master/.travis.yml
    if [ ! -d ${kafka_dir } ]; then
        wget http://www.us.apache.org/dist/kafka/0.8.2.1/kafka_2.10-0.8.2.1.tgz -O ${DOWNLOAD_DIR}/kafka.tgz
        mkdir -p ${kafka_dir} && tar xzf ${DOWNLOAD_DIR}/kafka.tgz -C ${kafka_dir} --strip-components 1
    fi

    nohup bash -c "cd ${kafka_dir} && bin/zookeeper-server-start.sh config/zookeeper.properties &"
    nohup bash -c "cd ${kafka_dir} && bin/kafka-server-start.sh config/server.properties &"
    sleep 5
    ${kafka_dir}/bin/kafka-topics.sh --create --partitions 1 --replication-factor 1 --topic case --zookeeper localhost:2181
}
