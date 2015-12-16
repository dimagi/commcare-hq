# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.db.models import Q

from corehq.sql_db.operations import HqRunPython


def check_for_subscriber_domain(apps, schema_editor):
    if apps.get_model('accounting', 'Subscriber').objects.filter(
        Q(domain=None) | Q(domain='')
    ):
        raise Exception("There exists a subscriber with no domain.")


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0006_remove_organization_field'),
    ]

    operations = {
        HqRunPython(check_for_subscriber_domain, reverse_code=lambda: None),
        migrations.AlterField(
            model_name='subscriber',
            name='domain',
            field=models.CharField(max_length=256, db_index=True),
            preserve_default=True,
        ),
    }
