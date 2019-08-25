# -*- coding: utf-8 -*-

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('pillow_retry', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='pillowerror',
            name='queued',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
    ]
