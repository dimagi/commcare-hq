# -*- coding: utf-8 -*-
# Generated by Django 1.11.11 on 2018-03-27 12:40
from __future__ import absolute_import
from __future__ import unicode_literals

from django.db import migrations

from corehq.apps.accounting.bootstrap.config.standard_user_limit_march_2018 import BOOTSTRAP_CONFIG
from corehq.apps.accounting.bootstrap.utils import ensure_plans



def _bootstrap_new_standard_user_limit(apps, schema_editor):
    ensure_plans(BOOTSTRAP_CONFIG, verbose=True, apps=apps)


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0020_payment_method__unique_together'),
    ]

    operations = [
        migrations.RunPython(_bootstrap_new_standard_user_limit),
    ]
