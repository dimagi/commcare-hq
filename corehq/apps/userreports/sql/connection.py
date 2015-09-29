

def get_engine_id(an_object):
    """
    Given an object, get the engine id for it.
    """
    # for now this only deals with data sources.
    from corehq.apps.userreports.models import DataSourceConfiguration
    assert isinstance(an_object, DataSourceConfiguration)
    return an_object.engine_id
