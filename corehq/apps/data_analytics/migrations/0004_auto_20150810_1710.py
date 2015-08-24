# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('data_analytics', '0003_auto_20150810_1710'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='maltrow',
            name='is_web_user',
        ),
    ]
