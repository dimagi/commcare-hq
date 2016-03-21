# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0014_add_queuedsms'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='PhoneNumber',
            new_name='PhoneBlacklist',
        ),
    ]
