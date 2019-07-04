# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations

from corehq.util.django_migrations import noop_migration


class Migration(migrations.Migration):

    dependencies = [
        ('sql_proxy_accessors', '0032_remove_get_cases_by_domain'),
    ]

    operations = [
        migrations.RunSQL("DROP FUNCTION IF EXISTS case_modified_since(TEXT, TIMESTAMP)")
    ]
