# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import uuidfield.fields

def _alter_to_uuid_sql_forawd(model, field):
    return 'ALTER TABLE "form_processor_{model}" ALTER COLUMN "{field}" TYPE uuid USING {field}::uuid;'.format(
        model=model, field=field
    )


def _alter_to_uuid_sql_reverse(model, field):
    return 'ALTER TABLE "form_processor_{model}" ALTER COLUMN "{field}" TYPE varchar(255);'.format(
        model=model, field=field
    )


def migrate_field_to_uuid(model, field, unique=True, db_index=True, null=False):
    forward = _alter_to_uuid_sql_forawd(model, field)
    reverse = _alter_to_uuid_sql_reverse(model, field)

    return migrations.RunSQL(
        forward,
        reverse,
        state_operations=[migrations.AlterField(
            model_name=model,
            name=field,
            field=uuidfield.fields.UUIDField(
                unique=unique,
                max_length=32,
                db_index=db_index,
                null=null),
            preserve_default=True,
        )]
    )

class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0045_auto_20151126_1350'),
    ]

    operations = [
        migrate_field_to_uuid('caseattachmentsql', 'attachment_id'),
        migrate_field_to_uuid('xformattachmentsql', 'attachment_id')
    ]
