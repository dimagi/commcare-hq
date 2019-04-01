# -*- coding: utf-8 -*-
# Generated by Django 1.11.16 on 2019-03-12 10:52
from __future__ import unicode_literals
from __future__ import absolute_import

from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration
from custom.icds_reports.utils.migrations import get_view_migrations

migrator = RawSQLMigration(('custom', 'icds_reports', 'migrations', 'sql_templates'))


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0108_child_cases_ccs_record_supervisor_id'),
    ]

    operations = [
        migrator.get_migration('update_tables45.sql'),

    ]
    operations.extend(get_view_migrations())

