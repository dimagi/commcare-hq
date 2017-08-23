import random

from corehq.sql_db.connections import connection_manager

READ_REPLICA_ROLLOUT_FACTOR = 0.01  # 1%


def get_engine_id(an_object):
    """
    Given an object, get the engine id for it.
    """
    # for now this only deals with data sources.
    from corehq.apps.userreports.models import DataSourceConfiguration
    assert isinstance(an_object, DataSourceConfiguration)
    if random.random() < READ_REPLICA_ROLLOUT_FACTOR:
        return connection_manager.get_read_replica_engine_id(an_object.engine_id)
    return an_object.engine_id
