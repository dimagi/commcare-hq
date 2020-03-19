from django.db import migrations

from custom.icds_reports.utils.migrations import create_index_migration
from corehq.sql_db.operations import RawSQLMigration


migrator = RawSQLMigration(('custom', 'icds_reports', 'migrations', 'sql_templates', 'database_views'))


class Migration(migrations.Migration):

    table_name = "daily_attendance"
    index_name = "ix_daily_attendance_month_state_id"
    columns = ['month', 'state_id']

    create_index_sql, drop_index_sql = create_index_migration(table_name, index_name, columns)

    atomic = False

    dependencies = [
        ('icds_reports', '0152_dashboarduseractivityreport'),
    ]

    operations = [
        migrations.RunSQL("ALTER TABLE daily_attendance ADD COLUMN state_id text"),
        migrations.RunSQL(
            sql=create_index_sql,
            reverse_sql=drop_index_sql,
        ),
    ]
