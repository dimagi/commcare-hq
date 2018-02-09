# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0014_caseattachmentsql_index_on_foreign_key'),
    ]

    operations = [
        migrations.AlterField(
            model_name='xformattachmentsql',
            name='xform',
            field=models.ForeignKey(related_query_name=b'attachment', related_name='attachments', db_column=b'form_uuid', to_field=b'form_uuid', to='form_processor.XFormInstanceSQL', on_delete=models.CASCADE),
            preserve_default=True,
        ),
    ]
