from corehq.db import DEFAULT_ENGINE_ID


def get_engine_id(object):
    """
    Given an object, get the engine id for it.
    """
    # for now this only deals with data sources.
    from corehq.apps.userreports.models import DataSourceConfiguration
    assert isinstance(object, DataSourceConfiguration)
    # we can swap this out to specify multiple engines when we want to support multiple databases/schemas
    return DEFAULT_ENGINE_ID
