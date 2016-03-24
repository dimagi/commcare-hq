# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0004_add_sqlivrbackend_sqlkookoobackend'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='sqlmobilebackend',
            unique_together=set([]),
        ),
    ]
