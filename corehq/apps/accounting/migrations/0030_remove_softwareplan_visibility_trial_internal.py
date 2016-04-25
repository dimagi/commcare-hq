# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0029_merge'),
    ]

    operations = [
        migrations.AlterField(
            model_name='softwareplan',
            name='visibility',
            field=models.CharField(default=b'INTERNAL', max_length=10, choices=[(b'PUBLIC', b'Anyone can subscribe'), (b'INTERNAL', b'Dimagi must create subscription'), (b'TRIAL', b'This is a Trial Plan')]),
            preserve_default=True,
        ),
    ]
