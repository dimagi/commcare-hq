from __future__ import absolute_import, unicode_literals

from celery.task import task

from corehq.apps.aggregate_ucrs.ingestion import populate_aggregate_table_data
from corehq.apps.aggregate_ucrs.models import AggregateTableDefinition
from corehq.apps.userreports.const import UCR_CELERY_QUEUE
from corehq.apps.userreports.sql import IndicatorSqlAdapter


@task(queue=UCR_CELERY_QUEUE, ignore_result=True)
def populate_aggregate_table_data_task(aggregate_table_id):
    definition = AggregateTableDefinition.objects.get(id=aggregate_table_id)
    return populate_aggregate_table_data(IndicatorSqlAdapter(definition))
