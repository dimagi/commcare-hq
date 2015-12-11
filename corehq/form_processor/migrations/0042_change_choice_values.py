# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0041_noop_specify_table_names'),
    ]

    operations = [
        migrations.AlterField(
            model_name='casetransaction',
            name='type',
            field=models.PositiveSmallIntegerField(choices=[(0, b'form'), (1, b'rebuild_with_reason'), (2, b'user_requested_rebuild'), (4, b'user_archived_rebuild'), (8, b'form_archive_rebuild'), (16, b'form_edit_rebuild'), (32, b'ledger')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='xforminstancesql',
            name='state',
            field=models.PositiveSmallIntegerField(default=0, choices=[(0, b'normal'), (1, b'archived'), (2, b'deprecated'), (4, b'duplicate'), (8, b'error'), (16, b'submission_error')]),
            preserve_default=True,
        ),
    ]
