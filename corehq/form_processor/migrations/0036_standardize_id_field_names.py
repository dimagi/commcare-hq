# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0035_remove_varchar_pattern_ops_indexes'),
    ]

    operations = [
        migrations.RenameField(
            model_name='caseattachmentsql',
            old_name='attachment_uuid',
            new_name='attachment_id',
        ),
        migrations.RenameField(
            model_name='casetransaction',
            old_name='form_uuid',
            new_name='form_id',
        ),
        migrations.RenameField(
            model_name='commcarecasesql',
            old_name='case_uuid',
            new_name='case_id',
        ),
        migrations.RenameField(
            model_name='commcarecasesql',
            old_name='location_uuid',
            new_name='location_id',
        ),
        migrations.RenameField(
            model_name='xformattachmentsql',
            old_name='attachment_uuid',
            new_name='attachment_id',
        ),
        migrations.RenameField(
            model_name='xforminstancesql',
            old_name='form_uuid',
            new_name='form_id',
        ),
        migrations.RunSQL(
            'ALTER TABLE "form_processor_xformattachmentsql" RENAME COLUMN "form_uuid" TO "form_id"',
            'ALTER TABLE "form_processor_xformattachmentsql" RENAME COLUMN "form_id" TO "form_uuid"',
            state_operations=[
                migrations.RemoveField(
                    model_name='xformattachmentsql',
                    name='xform',
                ),
                migrations.AddField(
                    model_name='xformattachmentsql',
                    name='form',
                    field=models.ForeignKey(related_query_name=b'attachment', related_name='attachment_set', to_field=b'form_id', to='form_processor.XFormInstanceSQL'),
                    preserve_default=False,
                ),
            ]
        ),
        migrations.RunSQL(
            'ALTER TABLE "form_processor_xformoperationsql" RENAME COLUMN "xform_id" TO "form_id"',
            'ALTER TABLE "form_processor_xformoperationsql" RENAME COLUMN "form_id" TO "xform_id"',
            state_operations=[
                migrations.RemoveField(
                    model_name='xformoperationsql',
                    name='xform',
                ),
                migrations.AddField(
                    model_name='xformoperationsql',
                    name='form',
                    field=models.ForeignKey(to='form_processor.XFormInstanceSQL', to_field=b'form_id'),
                    preserve_default=False,
                ),
            ]
        ),
        migrations.RunSQL(
            'ALTER TABLE "form_processor_caseattachmentsql" RENAME COLUMN "case_uuid" TO "case_id"',
            'ALTER TABLE "form_processor_caseattachmentsql" RENAME COLUMN "case_id" TO "case_uuid"',
            state_operations=[
                migrations.AlterField(
                    model_name='caseattachmentsql',
                    name='case',
                    field=models.ForeignKey(related_query_name=b'attachment', related_name='attachment_set', to_field=b'case_id', to='form_processor.CommCareCaseSQL'),
                    preserve_default=True,
                ),
            ]
        ),
        migrations.RunSQL(
            'ALTER TABLE "form_processor_casetransaction" RENAME COLUMN "case_uuid" TO "case_id"',
            'ALTER TABLE "form_processor_casetransaction" RENAME COLUMN "case_id" TO "case_uuid"',
            state_operations=[
                migrations.AlterField(
                    model_name='casetransaction',
                    name='case',
                    field=models.ForeignKey(related_query_name=b'transaction', related_name='transaction_set', to_field=b'case_id', to='form_processor.CommCareCaseSQL'),
                    preserve_default=True,
                ),
            ]
        ),
        migrations.RunSQL(
            'ALTER TABLE "form_processor_commcarecaseindexsql" RENAME COLUMN "case_uuid" TO "case_id"',
            'ALTER TABLE "form_processor_commcarecaseindexsql" RENAME COLUMN "case_id" TO "case_uuid"',
            state_operations=[
                migrations.AlterField(
                    model_name='commcarecaseindexsql',
                    name='case',
                    field=models.ForeignKey(related_query_name=b'index', related_name='index_set', to_field=b'case_id', to='form_processor.CommCareCaseSQL'),
                    preserve_default=True,
                ),
            ]
        ),
        migrations.AlterUniqueTogether(
            name='casetransaction',
            unique_together=set([('case', 'form_id')]),
        ),
    ]
