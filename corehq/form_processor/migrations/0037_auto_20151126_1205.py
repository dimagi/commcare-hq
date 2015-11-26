# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

NOOP = 'SELECT 1'


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0036_auto_20151126_1204'),
    ]

    operations = [
        migrations.RenameField(
            model_name='xforminstancesql',
            old_name='form_uuid',
            new_name='form_id',
        ),
        # workaround for https://code.djangoproject.com/ticket/25817
        # but another bug prevents squashing: https://code.djangoproject.com/ticket/25818
        migrations.RunSQL(
            NOOP, NOOP,
            state_operations=[
                migrations.AlterField(
                    model_name='xformattachmentsql',
                    name='form',
                    field=models.ForeignKey(related_query_name=b'attachment', related_name='attachments', to_field=b'form_id', to='form_processor.XFormInstanceSQL'),
                    preserve_default=True,
                ),
                migrations.AlterField(
                    model_name='xformoperationsql',
                    name='form',
                    field=models.ForeignKey(to='form_processor.XFormInstanceSQL', to_field=b'form_id'),
                    preserve_default=True,
                ),
            ]
        ),
    ]
