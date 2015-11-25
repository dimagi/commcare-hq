# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from corehq.blobs.migrate import assert_migration_complete
from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('blobs', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(assert_migration_complete("saved_exports"))
    ]
