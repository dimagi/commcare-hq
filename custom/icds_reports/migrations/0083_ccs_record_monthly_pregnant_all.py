# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2018-12-20 15:40
from __future__ import unicode_literals
from __future__ import absolute_import

from django.db import migrations
from corehq.sql_db.operations import RawSQLMigration


migrator = RawSQLMigration(('custom', 'icds_reports', 'migrations', 'sql_templates'))


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0082_ccs_record_monthly_closed'),
    ]

    operations = []
