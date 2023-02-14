from corehq.apps.es.client import get_client
from corehq.apps.es.exceptions import ESError  # noqa: F401


def get_es_new():
    # TODO: remove this (update where imported)
    return get_client()


def get_es_export():
    # TODO: remove this (update where imported)
    return get_client(for_export=True)
