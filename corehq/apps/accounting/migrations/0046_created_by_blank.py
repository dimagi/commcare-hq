# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0045_dimagi_contact_email_field'),
    ]

    operations = [
        migrations.AlterField(
            model_name='billingaccount',
            name='created_by',
            field=models.CharField(max_length=80, blank=True),
        ),
    ]
