from corehq.sql_db.operations import RawSQLMigration
from django.db import migrations

from custom.icds_reports.const import SQL_TEMPLATES_ROOT

migrator = RawSQLMigration((SQL_TEMPLATES_ROOT,))


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0083_ccs_record_monthly_pregnant_all'),
    ]

    operations = [
        migrator.get_migration('update_tables35.sql')
    ]
