# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

from django.core.management import call_command
from django.db import migrations


def update_es_mapping(*args, **kwargs):
    def _update_es_mapping():
        return call_command('update_es_mapping', 'app', noinput=True)
    return _update_es_mapping


class Migration(migrations.Migration):
    dependencies = [
        ('app_manager', '0005_latestenabledbuildprofiles_domain'),
    ]

    operations = [
        migrations.RunPython(update_es_mapping)
    ]
