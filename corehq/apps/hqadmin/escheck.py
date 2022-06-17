from corehq.elastic import get_es_new


def check_es_cluster_health():
    """Get an indicator of how the ElasticSearch cluster is running

    The color state of the cluster health is just a simple indicator for
    how a cluster is running. It'll mainly be useful for finding out if
    shards are in good/bad state (red).

    There are better realtime tools for monitoring ES clusters which
    should probably be looked at. specifically paramedic or bigdesk
    """
    es = get_es_new()  # assign to variable to avoid weak reference error
    cluster_health = es.cluster.health()
    return cluster_health['status']
