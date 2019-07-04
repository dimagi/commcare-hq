# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations

from corehq.util.django_migrations import noop_migration


class Migration(migrations.Migration):

    dependencies = [
        ('sql_proxy_accessors', '0030_exclude_deleted'),
    ]

    operations = [
        noop_migration()
    ]
