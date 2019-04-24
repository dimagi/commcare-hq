from __future__ import absolute_import, unicode_literals


def call_citus_experiment(parameterized_sql, params, data_source="Unknown"):
    from custom.icds_reports.tasks import run_citus_experiment_raw_sql
    run_citus_experiment_raw_sql.delay(parameterized_sql, params, data_source)
