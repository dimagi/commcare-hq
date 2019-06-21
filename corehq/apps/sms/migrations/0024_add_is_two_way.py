# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import

from django.db import migrations, models
import datetime


def set_pending_verification_numbers(apps, schema_editor):
    PhoneNumber = apps.get_model('sms', 'PhoneNumber')
    db_alias = schema_editor.connection.alias
    PhoneNumber.objects.using(db_alias).filter(verified=False).update(is_two_way=False, pending_verification=True)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0023_check_for_keyword_migration'),
    ]

    operations = [
        migrations.AddField(
            model_name='phonenumber',
            name='created_on',
            field=models.DateTimeField(default=datetime.datetime(2017, 1, 1, 0, 0), auto_now_add=True),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='phonenumber',
            name='is_two_way',
            field=models.BooleanField(default=True),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='phonenumber',
            name='pending_verification',
            field=models.BooleanField(default=False),
            preserve_default=False,
        ),
        migrations.RunPython(set_pending_verification_numbers, reverse_code=noop),
    ]
