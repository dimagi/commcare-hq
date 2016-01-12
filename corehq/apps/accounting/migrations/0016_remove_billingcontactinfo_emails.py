# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0015_datamigration_email_list'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='billingcontactinfo',
            name='emails',
        ),
    ]
