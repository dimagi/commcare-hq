from typing import Literal

import settings

AlertStr = Literal[
    'error',
    'warning',
    'info',
    'success',
]
ALERT_ERROR: AlertStr = 'error'
ALERT_WARNING: AlertStr = 'warning'
ALERT_INFO: AlertStr = 'info'
ALERT_SUCCESS: AlertStr = 'success'

COMMON_TAGS = {'environment': settings.SERVER_ENVIRONMENT}

TAG_UNKNOWN = '<unknown>'

# See PrometheusMetrics._gauge for documentation. This is only passed to
# PrometheusMetrics since it is one of PrometheusMetrics.accepted_gauge_params
PrometheusMultiprocessModeStr = Literal[
    'all',
    'liveall',
    'livesum',
    'max',
    'min',
]
MPM_ALL: PrometheusMultiprocessModeStr = 'all'
MPM_LIVEALL: PrometheusMultiprocessModeStr = 'liveall'
MPM_LIVESUM: PrometheusMultiprocessModeStr = 'livesum'
MPM_MAX: PrometheusMultiprocessModeStr = 'max'
MPM_MIN: PrometheusMultiprocessModeStr = 'min'
