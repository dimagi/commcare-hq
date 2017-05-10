'''
When a fact table is in the "needs_updating" state, it will be
selected for processing during the task that determines which
fact tables need updating.
'''
FACT_TABLE_NEEDS_UPDATING = 'needs_updating'

'''
When a fact table has reached the batch dumped state, it will
have dumped all newly relevant modified data into an intermediate
table to be processed.
'''
FACT_TABLE_BATCH_DUMPED = 'batch_dumped'

'''
When a fact table is in the ready state it has completed the
processing of the intermediate table and the fact table and
is now up to date.
'''
FACT_TABLE_READY = 'ready'

'''
When a fact table is in a failed state, it means that it
has failed to progress during one of the transitions due
to an error.
'''
FACT_TABLE_FAILED = 'failed'

'''
When a fact table is in a decommissioned state, it means
that it no process will attempt to re-process it unless
there is manual intervention.
'''
FACT_TABLE_DECOMMISSIONED = 'decommissioned'
