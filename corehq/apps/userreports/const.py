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
DATA_SOURCE_MISSING_APP_ERROR_MESSAGE = _(
    "Report builder data source doesn't reference an application. "
    "It is likely this report has been customized and it is no longer editable. "
)

UCR_SQL_BACKEND = "SQL"

DEFAULT_MAXIMUM_EXPANSION = 10
LENIENT_MAXIMUM_EXPANSION = 50

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

FILTER_INTERPOLATION_DOC_TYPES = {
    "CommCareCase": "type",
    "XFormInstance": "xmlns",
}

VALID_REFERENCED_DOC_TYPES = [
    'CommCareCase',
    'CommCareUser',
    'Location',
    'XFormInstance',
]

ASYNC_INDICATOR_QUEUE_TIME = timedelta(minutes=5)
ASYNC_INDICATOR_CHUNK_SIZE = 100
ASYNC_INDICATOR_MAX_RETRIES = 20

XFORM_CACHE_KEY_PREFIX = 'xform_to_json_cache'

NAMED_EXPRESSION_PREFIX = 'NamedExpression'
NAMED_FILTER_PREFIX = 'NamedFilter'


DATA_SOURCE_TYPE_STANDARD = 'standard'
DATA_SOURCE_TYPE_AGGREGATE = 'aggregate'


AGGGREGATION_TYPE_AVG = 'avg'
AGGGREGATION_TYPE_COUNT_UNIQUE = 'count_unique'
AGGGREGATION_TYPE_COUNT = 'count'
AGGGREGATION_TYPE_MIN = 'min'
AGGGREGATION_TYPE_MAX = 'max'
AGGGREGATION_TYPE_MONTH = 'month'
AGGGREGATION_TYPE_SUM = 'sum'
AGGGREGATION_TYPE_SIMPLE = 'simple'
AGGGREGATION_TYPE_YEAR = 'year'
AGGGREGATION_TYPE_NONZERO_SUM = 'nonzero_sum'
AGGGREGATION_TYPE_ARRAY_AGG_LAST_VALUE = 'array_agg_last_value'
