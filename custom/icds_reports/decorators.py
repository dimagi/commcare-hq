from __future__ import absolute_import, unicode_literals

from functools import wraps

from custom.icds_reports.tasks import run_citus_experiment


def compare_with_citus(dbaccessor_func):
    @wraps(dbaccessor_func)
    def _inner(*args, **kwargs):
        try:
            # TODO only compare % of queries
            run_citus_experiment.delay(dbaccessor_func, args, kwargs)
        except Exception:
            # TODO handle errors with delaying calls
            # likely to error json-izing args
            pass
        return dbaccessor_func(*args, **kwargs)

    return _inner
