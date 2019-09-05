# Generated by Django 1.11.16 on 2019-01-18 22:39

from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('custom', 'icds_reports', 'migrations', 'sql_templates'))


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0092_auto_20190129_0610'),
    ]

    operations = [
        migrator.get_migration('update_tables39.sql')
    ]
