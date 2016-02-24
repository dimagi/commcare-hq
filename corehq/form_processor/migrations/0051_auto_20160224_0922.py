# -*- coding: utf-8 -*-
from __future__ import unicode_literals

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
    ]
