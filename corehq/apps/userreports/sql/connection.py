

def get_engine_id(object):
    """
    Given an object, get the engine id for it.
    """
    # for now this only deals with data sources.
    from corehq.apps.userreports.models import DataSourceConfiguration
    assert isinstance(object, DataSourceConfiguration)
    return object.engine_id
