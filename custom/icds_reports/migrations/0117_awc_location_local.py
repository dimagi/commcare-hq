# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion

from corehq.sql_db.operations import RawSQLMigration
from custom.icds_reports.utils.migrations import get_view_migrations

migrator = RawSQLMigration(('custom', 'icds_reports', 'migrations', 'sql_templates', 'database_views'))


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0116_daily_attendance_index'),
    ]

    operations = [
        migrations.CreateModel(
            name='AwcLocationLocal',
            fields=[
                ('awclocation_ptr',
                 models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE,
                                      parent_link=True, primary_key=True, serialize=False,
                                      to='icds_reports.AwcLocation')),
            ],
            options={
                'db_table': 'awc_location_local',
                'managed': False,
            },
            bases=('icds_reports.awclocation',),
        ),
    ]
    operations.extend(get_view_migrations())
    operations.append(migrator.get_migration('service_delivery_monthly.sql'),)
