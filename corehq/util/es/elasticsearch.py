from django.conf import settings

if settings.ELASTICSEARCH_MAJOR_VERSION == 1:
    import elasticsearch
    from elasticsearch.exceptions import AuthorizationException
    from elasticsearch import (
        ConnectionError,
        ConnectionTimeout,
        Elasticsearch,
        ElasticsearchException,
        NotFoundError,
        SerializationError,
        ConflictError,
        TransportError,
        RequestError,
    )
    from elasticsearch.client import (
        IndicesClient,
        SnapshotClient,
    )
    from elasticsearch.helpers import bulk
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
    from elasticsearch2.helpers import bulk
else:
    raise ValueError("ELASTICSEARCH_MAJOR_VERSION must currently be 1 or 2")
