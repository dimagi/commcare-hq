# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations

from corehq.util.django_migrations import noop_migration


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0036_cleanup_models'),
    ]

    operations = [
        noop_migration(),
    ]
