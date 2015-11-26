# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import uuidfield.fields

from corehq.form_processor.utils.migration import migrate_field_to_uuid, migrate_field_with_foreign_keys_to_uuid, \
    ModelField, ForeignKeyField


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0035_remove_varchar_pattern_ops_indexes'),
    ]

    operations = [
        migrate_field_to_uuid('xforminstancesql', 'app_id', null=True),
        migrate_field_to_uuid('xforminstancesql', 'build_id', null=True),
        migrate_field_to_uuid('xforminstancesql', 'deprecated_form_id', null=True),
        migrate_field_to_uuid('xforminstancesql', 'deprecated_form_id', null=True),
        migrate_field_to_uuid('xforminstancesql', 'last_sync_token', null=True),
        migrate_field_to_uuid('xforminstancesql', 'orig_id', null=True),
        migrate_field_to_uuid('xforminstancesql', 'user_id', null=True),
        migrate_field_to_uuid('casetransaction', 'form_uuid', null=True),
        migrate_field_to_uuid('xformoperationsql', 'user', null=True),
        migrate_field_with_foreign_keys_to_uuid(
            ModelField('xforminstancesql', 'form_uuid', unique=True, db_index=True),
            [
                ForeignKeyField('xformattachmentsql', 'form_uuid', constraint='D89b6a5bce7bb3669f0bc9fe50022b06'),
                ForeignKeyField('xformoperationsql', 'xform_id', constraint='b006f200335a0a74b529d3ef054b2ad9'),
            ]
        ),
    ]
