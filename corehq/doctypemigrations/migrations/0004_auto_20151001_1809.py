# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations
from corehq.doctypemigrations.djangomigrations import assert_initial_complete
from corehq.doctypemigrations.migrator_instances import users_migration



class Migration(migrations.Migration):

    dependencies = [
        ('doctypemigrations', '0003_doctypemigration_cleanup_complete'),
    ]

    operations = [
        migrations.RunPython(assert_initial_complete(users_migration))
    ]
