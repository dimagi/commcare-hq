from django.conf import settings
from memoized import memoized

from corehq.util.es.elasticsearch import Elasticsearch

from .utils import ElasticJSONSerializer


def get_client(for_export=False):
    """Get an elasticsearch client instance.

    :param for_export: (optional boolean) specifies whether the returned
                          client should be optimized for slow export queries.
    :returns: `elasticsearch.Elasticsearch` instance.
    """
    if for_export:
        return _client_for_export()
    return _client_default()


@memoized
def _client_default():
    """
    Get a configured elasticsearch client instance.
    """
    return _client()


@memoized
def _client_for_export():
    """
    Get an elasticsearch client with settings more tolerant of slow queries
    (better suited for large exports).
    """
    return _client(
        retry_on_timeout=True,
        max_retries=3,
        timeout=300,  # query timeout in seconds
    )


def _client(**override_kw):
    """Configure an elasticsearch.Elasticsearch instance."""
    hosts = _elastic_hosts()
    client_kw = {
        "timeout": settings.ES_SEARCH_TIMEOUT,
        "serializer": ElasticJSONSerializer(),
    }
    client_kw.update(override_kw)
    return Elasticsearch(hosts, **client_kw)


def _elastic_hosts():
    """Render the host list for passing to an elasticsearch-py client."""
    parse_hosts = getattr(settings, 'ELASTICSEARCH_HOSTS', [])
    if not parse_hosts:
        parse_hosts.append(settings.ELASTICSEARCH_HOST)
    hosts = []
    for hostspec in parse_hosts:
        host, c, port = hostspec.partition(":")
        if port:
            port = int(port)
        else:
            port = settings.ELASTICSEARCH_PORT
        hosts.append({"host": host, "port": port})
    return hosts
