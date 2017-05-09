from django.db import models
from django_fsm import FSMField, transition, RETURN_VALUE

from .states import (
    FACT_TABLE_NEEDS_UPDATING,
    FACT_TABLE_BATCH_DUMPED,
    FACT_TABLE_READY,
    FACT_TABLE_FAILED,
    FACT_TABLE_DECOMMISSIONED,
)


class FactTableState(models.Model):
    domain = models.CharField(max_length=255)
    report_slug = models.CharField(max_length=255)
    state = FSMField(default=FACT_TABLE_NEEDS_UPDATING)
    last_modified = models.DateTimeField()
    last_batch_id = models.CharField(max_length=255)

    class Meta(object):
        index_together = ('domain', 'state')

    @transition(
        field=state,
        source=[FACT_TABLE_NEEDS_UPDATING, FACT_TABLE_FAILED],
        target=FACT_TABLE_BATCH_DUMPED,
        on_error=FACT_TABLE_FAILED,
    )
    def dump_to_intermediate_table(self):
        return

    @transition(
        field=state,
        source=FACT_TABLE_BATCH_DUMPED,
        target=FACT_TABLE_READY,
        on_error=FACT_TABLE_FAILED,
    )
    def process_intermediate_table(self):
        return

    @transition(
        field=state,
        source=FACT_TABLE_READY,
        target=FACT_TABLE_NEEDS_UPDATING,
        on_error=FACT_TABLE_FAILED
    )
    def queue(self):
        return

    @transition(
        field=state,
        source='*',
        target=FACT_TABLE_FAILED,
    )
    def fail(self):
        return

    @transition(
        field=state,
        source='*',
        target=FACT_TABLE_DECOMMISSIONED,
    )
    def decommission(self):
        return
