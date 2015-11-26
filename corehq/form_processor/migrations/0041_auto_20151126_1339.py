# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0040_auto_20151126_1332'),
    ]

    operations = [
        migrations.AlterField(
            model_name='caseattachmentsql',
            name='case',
            field=models.ForeignKey(related_query_name=b'attachment', related_name='attachment_set', to_field=b'case_id', to='form_processor.CommCareCaseSQL'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='xformattachmentsql',
            name='form',
            field=models.ForeignKey(related_query_name=b'attachment', related_name='attachment_set', to_field=b'form_id', to='form_processor.XFormInstanceSQL'),
            preserve_default=True,
        ),
    ]
