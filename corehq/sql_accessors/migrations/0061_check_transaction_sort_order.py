# Generated by Django 1.11.13 on 2018-07-03 20:36

from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'))


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0060_case_attachment_drops'),
    ]

    operations = [
        migrator.get_migration('compare_server_client_case_transaction_order.sql'),
    ]
