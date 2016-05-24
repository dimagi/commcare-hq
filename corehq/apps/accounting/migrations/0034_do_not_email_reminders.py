# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

from corehq.sql_db.operations import HqRunPython

def do_not_email_migration(apps, schema_editor):
    Subscription = apps.get_model("accounting", "Subscription")
    Subscription.objects.filter(do_not_email_invoice=True).update(do_not_email_reminder=True)

class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0033_merge'),
    ]

    operations = [
        migrations.RenameField(
            model_name='subscription',
            old_name='do_not_email',
            new_name='do_not_email_invoice',
        ),
        migrations.AddField(
            model_name='subscription',
            name='do_not_email_reminder',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
        HqRunPython(do_not_email_migration)
    ]
