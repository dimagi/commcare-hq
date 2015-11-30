# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0038_ledgervalue'),
    ]

    operations = [
        migrations.RenameField(
            model_name='ledgervalue',
            old_name='product_id',
            new_name='entry_id',
        ),
        migrations.AlterField(
            model_name='casetransaction',
            name='type',
            field=models.PositiveSmallIntegerField(choices=[(0, b'form'), (1, b'rebuild_with_reason'), (2, b'user_requested_rebuild'), (3, b'user_archived_rebuild'), (4, b'form_archive_rebuild'), (5, b'form_edit_rebuild'), (6, b'ledger')]),
            preserve_default=True,
        ),
    ]
