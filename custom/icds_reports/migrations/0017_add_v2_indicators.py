
from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('custom', 'icds_reports', 'migrations', 'sql_templates'))


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports',
         '0016_aggawcmonthly_aggccsrecordmonthly_aggchildhealthmonthly_aggdailyusageview_aggthrmonthly_awclocation_'),
    ]

    operations = [
        migrator.get_migration('update_tables9.sql'),
        migrator.get_migration('setup_agg_awc_daily.sql')
    ]
