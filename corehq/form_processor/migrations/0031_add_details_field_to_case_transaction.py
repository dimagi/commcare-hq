# -*- coding: utf-8 -*-

from django.db import models, migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0030_casetransaction_revoked'),
    ]

    operations = [
        migrations.AddField(
            model_name='casetransaction',
            name='details',
            field=jsonfield.fields.JSONField(default=dict),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='casetransaction',
            name='type',
            field=models.PositiveSmallIntegerField(choices=[(0, b'form'), (1, b'rebuild_with_reason'), (2, b'user_requested_rebuild'), (3, b'user_archived_rebuild'), (4, b'form_archive_rebuild'), (5, b'form_edit_rebuild')]),
            preserve_default=True,
        ),
    ]
