# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

from django.db import migrations

from corehq.util.django_migrations import noop_migration


class Migration(migrations.Migration):

    dependencies = [
        ('pillow_retry', '0003_auto_20151002_0944'),
    ]

    operations = [
        noop_migration(),
    ]
