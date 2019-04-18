from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.sql_db.connections import connection_manager


def get_engine_id(an_object, allow_read_replicas=False):
    """
    Given an object, get the engine id for it.
    """
    # for now this only deals with data sources.
    from corehq.apps.userreports.models import AbstractUCRDataSource
    assert isinstance(an_object, AbstractUCRDataSource)
    if allow_read_replicas:
        return connection_manager.get_load_balanced_read_db_alias(an_object.engine_id)
    return an_object.engine_id
