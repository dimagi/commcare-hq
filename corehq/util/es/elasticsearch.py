from django.conf import settings

if settings.ELASTICSEARCH_MAJOR_VERSION == 1:
    import elasticsearch
elif settings.ELASTICSEARCH_MAJOR_VERSION == 2:
    import elasticsearch2 as elasticsearch
elif settings.ELASTICSEARCH_MAJOR_VERSION == 7:
    import elasticsearch7 as elasticsearch
else:
    raise ValueError("ELASTICSEARCH_MAJOR_VERSION must currently be 1 or 2 or 7")


class VersionSpeific(object):
    secondary_module = None

    def __new__(cls, *args, **kwargs):
        import elasticsearch
        import elasticsearch2
        import elasticsearch7
        module = {
            1: elasticsearch,
            2: elasticsearch2,
            7: elasticsearch7
        }[settings.ELASTICSEARCH_MAJOR_VERSION]
        _class = getattr(module, cls.__name__)
        if cls.secondary_module:
            _class = getattr(
                getattr(module, cls.secondary_module),
                cls.__name__
            )
        else:
            _class = getattr(module, cls.__name__)
        return _class(*args, **kwargs)


class ConnectionError(VersionSpeific):
    pass


class ConnectionTimeout(VersionSpeific):
    pass


class Elasticsearch(VersionSpeific):
    pass


class ElasticsearchException(VersionSpeific):
    pass


class NotFoundError(VersionSpeific):
    pass


class SerializationError(VersionSpeific):
    pass


class ConflictError(VersionSpeific):
    pass


class TransportError(VersionSpeific, Exception):
    pass


class RequestError(VersionSpeific):
    pass


class IndicesClient(VersionSpeific):
    secondary_module = 'client'


class SnapshotClient(VersionSpeific):
    secondary_module = 'client'


class AuthorizationException(VersionSpeific):
    secondary_module = 'exceptions'


def bulk(*args, **kwargs):
    import elasticsearch
    import elasticsearch2
    import elasticsearch7
    module = {
        1: elasticsearch,
        2: elasticsearch2,
        7: elasticsearch7
    }[settings.ELASTICSEARCH_MAJOR_VERSION]
    return getattr(module.helpers, 'bulk')(*args, **kwargs)


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
