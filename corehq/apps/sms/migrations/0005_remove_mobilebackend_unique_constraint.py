# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations


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
