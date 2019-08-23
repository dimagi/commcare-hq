# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

import django.db.models.deletion
from django.db import migrations, models


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
