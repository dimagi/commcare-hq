# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

from corehq.form_processor.utils.migration import migrate_field_to_uuid, migrate_field_with_foreign_keys_to_uuid, \
    ModelField, ForeignKeyField


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0036_convert_form_fields_to_uuids'),
    ]

    operations = [
        migrate_field_to_uuid('caseattachmentsql', 'attachment_uuid', unique=True, db_index=True),
        migrate_field_to_uuid('commcarecaseindexsql', 'referenced_id', unique=False, db_index=False),
        migrate_field_to_uuid('commcarecasesql', 'closed_by', null=True),
        migrate_field_to_uuid('commcarecasesql', 'modified_by'),
        migrate_field_to_uuid('commcarecasesql', 'opened_by', null=True),
        migrate_field_to_uuid('commcarecasesql', 'owner_id'),
        migrate_field_to_uuid('xformattachmentsql', 'attachment_uuid', unique=True, db_index=True),
        migrate_field_with_foreign_keys_to_uuid(
            ModelField('commcarecasesql', 'case_uuid', unique=True, db_index=True),
            [
                ForeignKeyField('casetransaction', 'case_uuid', constraint='ff0710f9213660f903847c891a5d5762'),
                ForeignKeyField('commcarecaseindexsql', 'case_uuid', constraint='cfcdbfc04fcdbdaad9e930303c4ff2ef'),
                ForeignKeyField('caseattachmentsql', 'case_uuid', constraint='D5884f36fb7907982691c5f0dc3e05fb'),
            ]
        ),
    ]
