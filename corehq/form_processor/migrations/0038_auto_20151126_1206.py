# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0037_auto_20151126_1205'),
    ]

    operations = [
        migrations.AlterField(
            model_name='caseattachmentsql',
            name='case',
            field=models.ForeignKey(related_query_name=b'attachment', related_name='attachments', to_field=b'case_uuid', to='form_processor.CommCareCaseSQL'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='casetransaction',
            name='case',
            field=models.ForeignKey(related_query_name=b'transaction', related_name='transaction_set', to_field=b'case_uuid', to='form_processor.CommCareCaseSQL', db_index=False),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='commcarecaseindexsql',
            name='case',
            field=models.ForeignKey(related_query_name=b'index', related_name='index_set', to_field=b'case_uuid', to='form_processor.CommCareCaseSQL'),
            preserve_default=True,
        ),
    ]
