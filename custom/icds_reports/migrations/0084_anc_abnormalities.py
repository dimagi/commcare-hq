from __future__ import unicode_literals
from __future__ import absolute_import

from django.db import migrations
from corehq.sql_db.operations import RawSQLMigration
from custom.icds_reports.utils.migrations import get_view_migrations


migrator = RawSQLMigration(('custom', 'icds_reports', 'migrations', 'sql_templates'))


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0083_ccs_record_monthly_pregnant_all'),
    ]

    operations = [
        migrator.get_migration('update_tables35.sql')
    ]

    operations.extend(get_view_migrations())
