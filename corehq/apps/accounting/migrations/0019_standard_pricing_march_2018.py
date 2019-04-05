# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from __future__ import absolute_import

from django.db import migrations

from corehq.apps.accounting.bootstrap.config.standard_pricing_march_2018 import BOOTSTRAP_CONFIG
from corehq.apps.accounting.bootstrap.utils import ensure_plans



def _bootstrap_new_standard_pricing(apps, schema_editor):
    ensure_plans(BOOTSTRAP_CONFIG, verbose=True, apps=apps)


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0018_alter_nonnullable_char_fields'),
    ]

    operations = [
        migrations.RunPython(_bootstrap_new_standard_pricing),
    ]
