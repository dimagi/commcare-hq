# Generated by Django 1.11.13 on 2018-05-25 15:51

from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('corehq', 'apps', 'domain', 'migrations', 'sql_templates'))


class Migration(migrations.Migration):

    dependencies = [
        ('domain', '0002_auto_20171020_1428'),
    ]

    operations = [
        migrator.get_migration('update_tables1.sql'),
    ]
