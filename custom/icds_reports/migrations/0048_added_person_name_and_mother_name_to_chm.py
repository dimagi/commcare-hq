# Generated by Django 1.11.12 on 2018-05-16 12:57

from django.db import migrations
from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('custom', 'icds_reports', 'migrations', 'sql_templates'))


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0047_added_new_wasting_and_stunting_columns_to_views'),
    ]

    operations = [
        migrator.get_migration('update_tables22.sql'),
    ]
