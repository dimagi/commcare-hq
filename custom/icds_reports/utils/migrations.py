from __future__ import absolute_import
from __future__ import unicode_literals

from corehq.sql_db.operations import RawSQLMigration


def get_view_migrations():
    sql_views = [
        'awc_location_months.sql',
        'agg_awc_monthly.sql',
        'agg_ccs_record_monthly.sql',
        'agg_child_health_monthly.sql',
        'daily_attendance.sql',
        'agg_awc_daily.sql',
        'child_health_monthly.sql',
        'disha_indicators.sql',
        'ccs_record_monthly_view.sql'
    ]
    migrator = RawSQLMigration(('custom', 'icds_reports', 'migrations', 'sql_templates', 'database_views'))
    operations = []
    for view in sql_views:
        operations.append(migrator.get_migration(view))
    return operations
