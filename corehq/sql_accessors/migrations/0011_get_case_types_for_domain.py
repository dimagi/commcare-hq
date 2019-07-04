# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations

from corehq.util.django_migrations import noop_migration


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0010_update_state_type_values'),
    ]

    operations = [
        noop_migration()
    ]
