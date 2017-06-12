# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
from corehq.sql_db.operations import noop_migration


class Migration(migrations.Migration):

    dependencies = [
        ('userreports', '0001_initial'),
    ]

    operations = [
        noop_migration(),
    ]
