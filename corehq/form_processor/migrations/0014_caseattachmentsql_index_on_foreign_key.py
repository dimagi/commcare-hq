# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0013_caseattachmentsql'),
    ]

    operations = [
        migrations.AlterField(
            model_name='caseattachmentsql',
            name='case',
            field=models.ForeignKey(related_query_name=b'attachment', related_name='attachments', db_column=b'case_uuid', to_field=b'case_uuid', to='form_processor.CommCareCaseSQL'),
            preserve_default=True,
        ),
    ]
