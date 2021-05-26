from django.conf import settings

if settings.ELASTICSEARCH_MAJOR_VERSION == 1:
    raise RuntimeError(
        'Elasticsearch version 1 is no longer supported. Please upgrade Elasticsearch. Details: \n'
        'https://github.com/dimagi/commcare-cloud/blob/master/changelog/0032-upgrade-to-elasticsearch-2.4.6.yml'
    )
elif settings.ELASTICSEARCH_MAJOR_VERSION == 2:
    import elasticsearch2 as elasticsearch
    from elasticsearch2.exceptions import AuthorizationException
    from elasticsearch2 import (
        ConnectionError,
        ConflictError,
        ConnectionTimeout,
        Elasticsearch,
        ElasticsearchException,
        NotFoundError,
        SerializationError,
        TransportError,
        RequestError,
    )
    from elasticsearch2.client import (
        IndicesClient,
        SnapshotClient,
    )
    from elasticsearch2.helpers import bulk, scan
elif settings.ELASTICSEARCH_MAJOR_VERSION == 7:
    import elasticsearch7 as elasticsearch
    from elasticsearch7.exceptions import AuthorizationException
    from elasticsearch7 import (
        ConnectionError,
        ConflictError,
        ConnectionTimeout,
        Elasticsearch,
        ElasticsearchException,
        NotFoundError,
        SerializationError,
        TransportError,
        RequestError,
    )
    from elasticsearch7.client import (
        IndicesClient,
        SnapshotClient,
    )
    from elasticsearch7.helpers import bulk, scan
else:
    raise ValueError("ELASTICSEARCH_MAJOR_VERSION must currently be 2 or 7, given {}".format(
        settings.ELASTICSEARCH_MAJOR_VERSION))


__all__ = [
    'AuthorizationException',
    'ConflictError',
    'ConnectionError',
    'ConnectionTimeout',
    'Elasticsearch',
    'ElasticsearchException',
    'IndicesClient',
    'NotFoundError',
    'RequestError',
    'SerializationError',
    'SnapshotClient',
    'TransportError',
    'bulk',
    'elasticsearch',
]
