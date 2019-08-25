# -*- coding: utf-8 -*-

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0014_caseattachmentsql_index_on_foreign_key'),
    ]

    operations = [
        migrations.AlterField(
            model_name='xformattachmentsql',
            name='xform',
            field=models.ForeignKey(related_query_name=b'attachment', related_name='attachments', db_column='form_uuid', to_field='form_uuid', to='form_processor.XFormInstanceSQL', on_delete=models.CASCADE),
            preserve_default=True,
        ),
    ]
