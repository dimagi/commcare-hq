# -*- coding: utf-8 -*-

from django.db import models, migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0018_check_for_phone_number_migration'),
    ]

    operations = [
        migrations.AddField(
            model_name='selfregistrationinvitation',
            name='android_only',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='selfregistrationinvitation',
            name='custom_user_data',
            field=jsonfield.fields.JSONField(default=dict),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='selfregistrationinvitation',
            name='require_email',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
    ]
