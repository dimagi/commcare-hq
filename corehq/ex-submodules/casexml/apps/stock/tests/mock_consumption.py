from datetime import datetime, timedelta

from dimagi.utils import parsing as dateparse

from casexml.apps.stock.consumption import (
    ConsumptionConfiguration,
    compute_daily_consumption_from_transactions,
)

to_ts = dateparse.json_format_datetime
now = datetime.utcnow()


def ago(days):
    return now - timedelta(days=days)


# note that you must add inferred consumption transactions manually to txdata
def mock_consumption(txdata, window, params=None):
    default_params = {'min_window': 0, 'min_periods': 0}
    params = params or {}
    default_params.update(params)
    config = ConsumptionConfiguration(**default_params)
    return compute_daily_consumption_from_transactions(
        txdata,
        ago(window),
        config,
    )
