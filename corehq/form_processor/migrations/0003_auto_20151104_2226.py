# -*- coding: utf-8 -*-

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0002_xformattachmentsql'),
    ]

    operations = [
        migrations.AlterField(
            model_name='xformattachmentsql',
            name='xform',
            field=models.ForeignKey(to='form_processor.XFormInstanceSQL', to_field='form_uuid', on_delete=models.CASCADE),
            preserve_default=True,
        ),
    ]
