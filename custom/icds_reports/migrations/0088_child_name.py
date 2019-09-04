# Generated by Django 1.11.16 on 2019-01-18 22:39

from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('custom', 'icds_reports', 'migrations', 'sql_templates'))


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0087_death_dates'),
    ]

    operations = [
        migrator.get_migration('update_tables37.sql')
    ]
