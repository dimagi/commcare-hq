from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0050_allow_null_content_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='casetransaction',
            name='type',
            field=models.PositiveSmallIntegerField(choices=[(1, 'form'), (2, 'rebuild_with_reason'), (4, 'user_requested_rebuild'), (8, 'user_archived_rebuild'), (16, 'form_archive_rebuild'), (32, 'form_edit_rebuild'), (64, 'ledger')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='commcarecaseindexsql',
            name='relationship_id',
            field=models.PositiveSmallIntegerField(choices=[(1, 'child'), (2, 'extension')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='xforminstancesql',
            name='state',
            field=models.PositiveSmallIntegerField(default=1, choices=[(1, 'normal'), (2, 'archived'), (4, 'deprecated'), (8, 'duplicate'), (16, 'error'), (32, 'submission_error'), (64, 'deleted')]),
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
