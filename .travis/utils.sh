install_elasticsearch() {
    es_version=0.90.13

    echo "Installing elasticsearch version ${es_version}"

    wget "https://download.elastic.co/elasticsearch/elasticsearch/elasticsearch-${es_version}.tar.gz" -O elasticsearch.tar.gz

    tar xvzf elasticsearch.tar.gz -C elasticsearch
    nohup bash -c "cd elasticsearch-${es_version} && bin/elasticsearch &"
    sleep 5
}
