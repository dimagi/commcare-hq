from django.conf import settings
from memoized import memoized

from corehq.util.es.elasticsearch import Elasticsearch

from .utils import ElasticJSONSerializer


CLIENT_DEFAULT = "default"
CLIENT_EXPORT = "export"


def get_client(client_type=CLIENT_DEFAULT):
    """Get an elasticsearch client instance.

    :param client_type: (optional) specifies the type of elasticsearch client
                        needed (default=`CLIENT_DEFAULT`)
    :returns: `elasticsearch.Elasticsearch` instance.
    """
    if client_type not in CLIENT_TYPES:
        raise ValueError(f"invalid client type: {client_type!r} "
                         f"(must be one of {list(CLIENT_TYPES)})")
    return CLIENT_TYPES[client_type]()


@memoized
def _client_default():
    """
    Get a configured elasticsearch client instance.
    Returns an elasticsearch.Elasticsearch instance.
    """
    return _client()


@memoized
def _client_export():
    """
    Get an elasticsearch client with settings geared towards exports.
    Returns an elasticsearch.Elasticsearch instance.
    """
    return _client(
        retry_on_timeout=True,
        max_retries=3,
        timeout=300,  # query timeout in seconds
    )


CLIENT_TYPES = {
    CLIENT_DEFAULT: _client_default,
    CLIENT_EXPORT: _client_export,
}


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
