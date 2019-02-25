# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):
    initial = True

    dependencies = [
    ]

    operations = [
        # necessary for tests
        migrations.RunSQL("CREATE EXTENSION IF NOT EXISTS citus;"),
        migrations.RunSQL("SELECT * from master_add_node('citus_worker1_1', 5432);"),
        migrations.RunSQL("SELECT * from master_add_node('citus_worker2_1', 5432);"),
    ]
