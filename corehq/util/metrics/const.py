import settings

ALERT_ERROR = 'error'
ALERT_WARNING = 'warning'
ALERT_INFO = 'info'
ALERT_SUCCESS = 'success'

COMMON_TAGS = {'environment': settings.SERVER_ENVIRONMENT}

TAG_UNKNOWN = '<unknown>'

# Prometheus multiprocess_mode options
MPM_ALL = 'all'
MPM_LIVEALL = 'liveall'
MPM_LIVESUM = 'livesum'
MPM_MAX = 'max'
MPM_MIN = 'min'

# Datadog tags
MODULE_NAME_TAG = "module_name"

# These tags will only be added for domains with FF DETAILED_TAGGING enabled
GATED_DETAILED_TAGS = {MODULE_NAME_TAG}
