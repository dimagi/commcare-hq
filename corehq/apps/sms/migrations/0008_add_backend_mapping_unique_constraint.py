# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0007_check_for_backend_migration'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='sqlmobilebackendmapping',
            unique_together=set([('domain', 'backend_type', 'prefix')]),
        ),
    ]
