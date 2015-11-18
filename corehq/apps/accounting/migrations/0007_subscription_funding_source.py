# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0006_remove_organization_field'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscription',
            name='funding_source',
            field=models.CharField(default=b'CLIENT', max_length=25, choices=[(b'DIMAGI', b'Dimagi'), (b'CLIENT', b'Client Funding'), (b'EXTERNAL', b'External Funding')]),
            preserve_default=True,
        ),
    ]
