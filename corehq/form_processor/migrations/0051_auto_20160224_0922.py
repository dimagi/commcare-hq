# -*- coding: utf-8 -*-

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0050_allow_null_content_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='casetransaction',
            name='type',
            field=models.PositiveSmallIntegerField(choices=[(1, b'form'), (2, b'rebuild_with_reason'), (4, b'user_requested_rebuild'), (8, b'user_archived_rebuild'), (16, b'form_archive_rebuild'), (32, b'form_edit_rebuild'), (64, b'ledger')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='commcarecaseindexsql',
            name='relationship_id',
            field=models.PositiveSmallIntegerField(choices=[(1, b'child'), (2, b'extension')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='xforminstancesql',
            name='state',
            field=models.PositiveSmallIntegerField(default=1, choices=[(1, b'normal'), (2, b'archived'), (4, b'deprecated'), (8, b'duplicate'), (16, b'error'), (32, b'submission_error'), (64, b'deleted')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='caseattachmentsql',
            name='blob_id',
            field=models.CharField(default=None, max_length=255),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='caseattachmentsql',
            name='identifier',
            field=models.CharField(default=None, max_length=255),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='caseattachmentsql',
            name='md5',
            field=models.CharField(default=None, max_length=255),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='caseattachmentsql',
            name='name',
            field=models.CharField(default=None, max_length=255, db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='commcarecaseindexsql',
            name='domain',
            field=models.CharField(default=None, max_length=255),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='commcarecaseindexsql',
            name='identifier',
            field=models.CharField(default=None, max_length=255),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='commcarecaseindexsql',
            name='referenced_id',
            field=models.CharField(default=None, max_length=255),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='commcarecaseindexsql',
            name='referenced_type',
            field=models.CharField(default=None, max_length=255),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='commcarecasesql',
            name='domain',
            field=models.CharField(default=None, max_length=255),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='ledgervalue',
            name='case_id',
            field=models.CharField(default=None, max_length=255, db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='ledgervalue',
            name='entry_id',
            field=models.CharField(default=None, max_length=100, db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='ledgervalue',
            name='section_id',
            field=models.CharField(default=None, max_length=100, db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='xformattachmentsql',
            name='blob_id',
            field=models.CharField(default=None, max_length=255),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='xformattachmentsql',
            name='md5',
            field=models.CharField(default=None, max_length=255),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='xformattachmentsql',
            name='name',
            field=models.CharField(default=None, max_length=255, db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='xforminstancesql',
            name='domain',
            field=models.CharField(default=None, max_length=255),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='xforminstancesql',
            name='form_id',
            field=models.CharField(default=None, unique=True, max_length=255, db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='xformoperationsql',
            name='operation',
            field=models.CharField(default=None, max_length=255),
            preserve_default=True,
        ),
        migrations.AlterModelTable(
            name='ledgervalue',
            table='form_processor_ledgervalue',
        ),
    ]
