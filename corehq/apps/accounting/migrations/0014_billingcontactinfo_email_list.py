# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

import json_field.fields


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0013_forbid_feature_type_any'),
    ]

    operations = [
        migrations.AddField(
            model_name='billingcontactinfo',
            name='email_list',
            field=json_field.fields.JSONField(default=[], help_text='We will email communications regarding your account to the emails specified here.', verbose_name='Contact Emails'),
            preserve_default=True,
        ),
    ]
