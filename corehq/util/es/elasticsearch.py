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
    raise RuntimeError(
        'Elasticsearch version 5 is no longer supported. Please upgrade Elasticsearch.\n'
        'Details - https://commcare-cloud.readthedocs.io/en/latest/changelog/0087-upgrade-to-es-6.html'
    )
elif settings.ELASTICSEARCH_MAJOR_VERSION == 6:
    import elasticsearch6 as elasticsearch
    from elasticsearch6 import (
        ConflictError,
        ConnectionError,
        ConnectionTimeout,
        Elasticsearch,
        ElasticsearchException,
        NotFoundError,
        RequestError,
        SerializationError,
        TransportError,
    )
    from elasticsearch6.client import IndicesClient, SnapshotClient
    from elasticsearch6.exceptions import AuthorizationException
    from elasticsearch6.helpers import BulkIndexError, bulk
else:
    raise ValueError("ELASTICSEARCH_MAJOR_VERSION must currently be 5 or 6, given {}".format(
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
