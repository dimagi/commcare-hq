# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

NOOP = 'SELECT 1'


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0039_auto_20151126_1207'),
    ]

    operations = [
        migrations.RenameField(
            model_name='commcarecasesql',
            old_name='case_uuid',
            new_name='case_id',
        ),
        # workaround for https://code.djangoproject.com/ticket/25817
        # but another bug prevents squashing: https://code.djangoproject.com/ticket/25818
        migrations.RunSQL(
            NOOP, NOOP,
            state_operations=[
                migrations.AlterField(
                    model_name='caseattachmentsql',
                    name='case',
                    field=models.ForeignKey(related_query_name=b'attachment', related_name='attachments', to_field=b'case_id', to='form_processor.CommCareCaseSQL'),
                    preserve_default=True,
                ),
                migrations.AlterField(
                    model_name='casetransaction',
                    name='case',
                    field=models.ForeignKey(related_query_name=b'transaction', related_name='transaction_set', to_field=b'case_id', to='form_processor.CommCareCaseSQL', db_index=False),
                    preserve_default=True,
                ),
                migrations.AlterField(
                    model_name='commcarecaseindexsql',
                    name='case',
                    field=models.ForeignKey(related_query_name=b'index', related_name='index_set', to_field=b'case_id', to='form_processor.CommCareCaseSQL'),
                    preserve_default=True,
                ),
            ]
        ),
    ]
