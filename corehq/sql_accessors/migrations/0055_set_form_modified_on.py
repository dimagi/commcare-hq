# Generated by Django 1.10.7 on 2017-07-06 21:18

from django.db import migrations

from corehq.form_processor.models import XFormInstance, XFormOperation
from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'), {
    'FORM_STATE_ARCHIVED': XFormInstance.ARCHIVED,
    'FORM_STATE_NORMAL': XFormInstance.NORMAL,
    'FORM_OPERATION_ARCHIVE': XFormOperation.ARCHIVE,
    'FORM_OPERATION_UNARCHIVE': XFormOperation.UNARCHIVE,
})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0054_drop_reindexa_accessor_functions'),
    ]

    operations = [
        migrator.get_migration('archive_unarchive_form2.sql'),
    ]
