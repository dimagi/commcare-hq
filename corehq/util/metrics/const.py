import settings

from .typing import AlertStr, PrometheusMultiprocessModeStr

ALERT_ERROR: AlertStr = 'error'
ALERT_WARNING: AlertStr = 'warning'
ALERT_INFO: AlertStr = 'info'
ALERT_SUCCESS: AlertStr = 'success'

COMMON_TAGS = {'environment': settings.SERVER_ENVIRONMENT}

TAG_UNKNOWN = '<unknown>'

MPM_ALL: PrometheusMultiprocessModeStr = 'all'
MPM_LIVEALL: PrometheusMultiprocessModeStr = 'liveall'
MPM_LIVESUM: PrometheusMultiprocessModeStr = 'livesum'
MPM_MAX: PrometheusMultiprocessModeStr = 'max'
MPM_MIN: PrometheusMultiprocessModeStr = 'min'
