from __future__ import absolute_import
from datetime import timedelta
from django.utils.translation import ugettext_lazy as _
from corehq.apps.change_feed import topics

REPORT_BUILDER_EVENTS_KEY = 'REPORT_BUILDER_EVENTS_KEY'

DATA_SOURCE_NOT_FOUND_ERROR_MESSAGE = _(
    'Sorry! There was a problem viewing your report. '
    'This likely occurred because the application associated with the report was deleted. '
    'In order to view this data using the Report Builder you will have to delete this report '
    'and then build it again. Click below to delete it.'
)

UCR_SQL_BACKEND = "SQL"
UCR_ES_BACKEND = "ES"
UCR_LABORATORY_BACKEND = "LABORATORY"
UCR_ES_PRIMARY = "LAB_ES_PRIMARY"

UCR_BACKENDS = [UCR_SQL_BACKEND, UCR_ES_BACKEND]
UCR_SUPPORT_BOTH_BACKENDS = (UCR_LABORATORY_BACKEND, UCR_ES_PRIMARY)

DEFAULT_MAXIMUM_EXPANSION = 10

UCR_CELERY_QUEUE = 'ucr_queue'
UCR_INDICATOR_CELERY_QUEUE = 'ucr_indicator_queue'

KAFKA_TOPICS = (
    topics.CASE,
    topics.CASE_SQL,
    topics.FORM,
    topics.FORM_SQL,
    topics.LOCATION,
    topics.COMMCARE_USER,
)

VALID_REFERENCED_DOC_TYPES = [
    'CommCareCase',
    'CommCareUser',
    'Location',
    'XFormInstance',
]

ASYNC_INDICATOR_QUEUE_TIME = timedelta(minutes=5)
ASYNC_INDICATOR_CHUNK_SIZE = 10

XFORM_CACHE_KEY_PREFIX = 'xform_to_json_cache'
