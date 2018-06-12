from __future__ import absolute_import, unicode_literals
from corehq.apps.aggregate_ucrs.ingestion import populate_aggregate_table_data


def populate_aggregate_table_data_task(aggregate_table_adapter):
    return populate_aggregate_table_data(aggregate_table_adapter)
