# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2017-06-27 20:52
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('phonelog', '0009_userentry_server_date'),
    ]

    operations = [
        migrations.AlterModelTable(
            name='devicereportentry',
            table='phonelog_devicereportentry',
        ),
        migrations.RenameModel(
            old_name='DeviceReportEntry',
            new_name='OldDeviceReportEntry',
        ),
    ]
