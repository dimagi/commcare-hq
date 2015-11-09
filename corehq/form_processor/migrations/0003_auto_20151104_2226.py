# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0002_xformattachmentsql'),
    ]

    operations = [
        migrations.AlterField(
            model_name='xformattachmentsql',
            name='xform',
            field=models.ForeignKey(to='form_processor.XFormInstanceSQL', to_field=b'form_uuid'),
            preserve_default=True,
        ),
    ]
