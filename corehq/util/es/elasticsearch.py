from django.conf import settings

if settings.ELASTICSEARCH_MAJOR_VERSION == 1:
    raise RuntimeError(
        'Elasticsearch version 1 is no longer supported. Please upgrade Elasticsearch. Details: \n'
        'https://github.com/dimagi/commcare-cloud/blob/master/changelog/0032-upgrade-to-elasticsearch-2.4.6.yml'
    )
elif settings.ELASTICSEARCH_MAJOR_VERSION == 2:
    raise RuntimeError(
        'Elasticsearch version 2 is no longer supported. Please upgrade Elasticsearch. Details: \n'
        'Reindex steps - \n'
        '\t https://commcare-cloud.readthedocs.io/en/latest/changelog/0075-reindex-all-indexes-for-es-upgrade.html'
        'Upgrade steps - \n'
        '\t https://commcare-cloud.readthedocs.io/en/latest/changelog/0076-upgrade-to-es-5.html'
    )
elif settings.ELASTICSEARCH_MAJOR_VERSION == 5:
    import elasticsearch5 as elasticsearch
    from elasticsearch5.exceptions import AuthorizationException
    from elasticsearch5 import (
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
    from elasticsearch5.client import (
        IndicesClient,
        SnapshotClient,
    )
    from elasticsearch5.helpers import BulkIndexError, bulk
else:
    raise ValueError("ELASTICSEARCH_MAJOR_VERSION must currently be 2 or 5, given {}".format(
        settings.ELASTICSEARCH_MAJOR_VERSION))


__all__ = [
    'AuthorizationException',
    'BulkIndexError',
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
