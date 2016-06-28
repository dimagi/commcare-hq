# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

from corehq.sql_db.operations import HqRunPython


def check_no_nonnull_date_received(apps, schema_editor):
    assert not apps.get_model('accounting', 'Invoice').objects.filter(date_received__isnull=False).exists()
    assert not apps.get_model('accounting', 'WireInvoice').objects.filter(date_received__isnull=False).exists()


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0034_do_not_email_reminders'),
    ]

    operations = [
        HqRunPython(check_no_nonnull_date_received),
        migrations.RemoveField(
            model_name='invoice',
            name='date_received',
        ),
        migrations.RemoveField(
            model_name='wireinvoice',
            name='date_received',
        ),
    ]
