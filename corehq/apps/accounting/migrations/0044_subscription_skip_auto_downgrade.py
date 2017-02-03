# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0043_bootstrap_location_restrictions'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscription',
            name='skip_auto_downgrade',
            field=models.BooleanField(default=False),
        ),
    ]
