# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import uuidfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0035_remove_varchar_pattern_ops_indexes'),
    ]

    operations = [
        migrations.RunSQL(
            'ALTER TABLE "form_processor_xforminstancesql" ALTER COLUMN "app_id" TYPE uuid USING app_id::uuid',
            'ALTER TABLE "form_processor_xforminstancesql" ALTER COLUMN "app_id" TYPE varchar(255)',
            state_operations=[migrations.AlterField(
                model_name='xforminstancesql',
                name='app_id',
                field=uuidfield.fields.UUIDField(max_length=32, null=True),
                preserve_default=True,
            )]
        ),
        migrations.RunSQL(
            'ALTER TABLE "form_processor_xforminstancesql" ALTER COLUMN "build_id" TYPE uuid USING build_id::uuid',
            'ALTER TABLE "form_processor_xforminstancesql" ALTER COLUMN "build_id" TYPE varchar(255)',
            state_operations=[migrations.AlterField(
                model_name='xforminstancesql',
                name='build_id',
                field=uuidfield.fields.UUIDField(max_length=32, null=True),
                preserve_default=True,
            )]
        ),
        migrations.RunSQL(
            'ALTER TABLE "form_processor_xforminstancesql" ALTER COLUMN "deprecated_form_id" TYPE uuid USING deprecated_form_id::uuid',
            'ALTER TABLE "form_processor_xforminstancesql" ALTER COLUMN "deprecated_form_id" TYPE varchar(255)',
            state_operations=[migrations.AlterField(
                model_name='xforminstancesql',
                name='deprecated_form_id',
                field=uuidfield.fields.UUIDField(max_length=32, null=True),
                preserve_default=True,
            )]
        ),
        migrations.RunSQL(
            '''
            ALTER TABLE form_processor_xformattachmentsql DROP CONSTRAINT "D89b6a5bce7bb3669f0bc9fe50022b06";
            ALTER TABLE form_processor_xformoperationsql DROP CONSTRAINT "b006f200335a0a74b529d3ef054b2ad9";
            ALTER TABLE "form_processor_xformoperationsql" ALTER COLUMN "xform_id" TYPE uuid USING xform_id::uuid;
            ALTER TABLE "form_processor_xformattachmentsql" ALTER COLUMN "form_uuid" TYPE uuid USING form_uuid::uuid;
            ALTER TABLE "form_processor_xforminstancesql" ALTER COLUMN "form_uuid" TYPE uuid USING form_uuid::uuid;
            ALTER TABLE "form_processor_xformattachmentsql" ADD CONSTRAINT "D89b6a5bce7bb3669f0bc9fe50022b06"
                FOREIGN KEY (form_uuid) REFERENCES form_processor_xforminstancesql(form_uuid) DEFERRABLE INITIALLY DEFERRED;
            ALTER TABLE "form_processor_xformoperationsql" ADD CONSTRAINT "b006f200335a0a74b529d3ef054b2ad9"
                FOREIGN KEY (xform_id) REFERENCES form_processor_xforminstancesql(form_uuid) DEFERRABLE INITIALLY DEFERRED;
            ''',
            '''
            ALTER TABLE form_processor_xformattachmentsql DROP CONSTRAINT "D89b6a5bce7bb3669f0bc9fe50022b06";
            ALTER TABLE form_processor_xformoperationsql DROP CONSTRAINT "b006f200335a0a74b529d3ef054b2ad9";
            ALTER TABLE "form_processor_xformoperationsql" ALTER COLUMN "xform_id" TYPE varchar(255);
            ALTER TABLE "form_processor_xformattachmentsql" ALTER COLUMN "form_uuid" TYPE varchar(255);
            ALTER TABLE "form_processor_xforminstancesql" ALTER COLUMN "form_uuid" TYPE varchar(255);
            ALTER TABLE "form_processor_xformattachmentsql" ADD CONSTRAINT "D89b6a5bce7bb3669f0bc9fe50022b06"
                FOREIGN KEY (form_uuid) REFERENCES form_processor_xforminstancesql(form_uuid) DEFERRABLE INITIALLY DEFERRED;
            ALTER TABLE "form_processor_xformoperationsql" ADD CONSTRAINT "b006f200335a0a74b529d3ef054b2ad9"
                FOREIGN KEY (xform_id) REFERENCES form_processor_xforminstancesql(form_uuid) DEFERRABLE INITIALLY DEFERRED;
            ''',
            state_operations=[migrations.AlterField(
                model_name='xforminstancesql',
                name='form_uuid',
                field=uuidfield.fields.UUIDField(unique=True, max_length=32, db_index=True),
                preserve_default=True,
            )]
        ),
        migrations.RunSQL(
            'ALTER TABLE "form_processor_xforminstancesql" ALTER COLUMN "last_sync_token" TYPE uuid USING last_sync_token::uuid',
            'ALTER TABLE "form_processor_xforminstancesql" ALTER COLUMN "last_sync_token" TYPE varchar(255)',
            state_operations=[migrations.AlterField(
                model_name='xforminstancesql',
                name='last_sync_token',
                field=uuidfield.fields.UUIDField(max_length=32, null=True),
                preserve_default=True,
            )]
        ),
        migrations.RunSQL(
            'ALTER TABLE "form_processor_xforminstancesql" ALTER COLUMN "orig_id" TYPE uuid USING orig_id::uuid',
            'ALTER TABLE "form_processor_xforminstancesql" ALTER COLUMN "orig_id" TYPE varchar(255)',
            state_operations=[migrations.AlterField(
                model_name='xforminstancesql',
                name='orig_id',
                field=uuidfield.fields.UUIDField(max_length=32, null=True),
                preserve_default=True,
            )]
        ),
        migrations.RunSQL(
            'ALTER TABLE "form_processor_xforminstancesql" ALTER COLUMN "user_id" TYPE uuid USING user_id::uuid',
            'ALTER TABLE "form_processor_xforminstancesql" ALTER COLUMN "user_id" TYPE varchar(255)',
            state_operations=[migrations.AlterField(
                model_name='xforminstancesql',
                name='user_id',
                field=uuidfield.fields.UUIDField(max_length=32, null=True),
                preserve_default=True,
            )]
        ),
        migrations.RunSQL(
            'ALTER TABLE "form_processor_casetransaction" ALTER COLUMN "form_uuid" TYPE uuid USING form_uuid::uuid',
            'ALTER TABLE "form_processor_casetransaction" ALTER COLUMN "form_uuid" TYPE varchar(255)',
            state_operations=[migrations.AlterField(
                model_name='casetransaction',
                name='form_uuid',
                field=uuidfield.fields.UUIDField(max_length=32, null=True),
                preserve_default=True,
            )]
        ),
        migrations.RunSQL(
            'ALTER TABLE "form_processor_xformoperationsql" ALTER COLUMN "user" TYPE uuid USING user::uuid',
            'ALTER TABLE "form_processor_xformoperationsql" ALTER COLUMN "user" TYPE varchar(255)',
            state_operations=[migrations.AlterField(
                model_name='xformoperationsql',
                name='user',
                field=uuidfield.fields.UUIDField(max_length=32, null=True),
                preserve_default=True,
            )]
        ),
    ]
