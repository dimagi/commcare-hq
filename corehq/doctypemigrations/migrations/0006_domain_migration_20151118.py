# -*- coding: utf-8 -*-

from django.db import migrations
from corehq.doctypemigrations.djangomigrations import assert_initial_complete
from corehq.doctypemigrations.migrator_instances import domains_migration



class Migration(migrations.Migration):

    dependencies = [
        ('doctypemigrations', '0005_auto_20151013_0819'),
    ]

    operations = {
        migrations.RunPython(assert_initial_complete(domains_migration))
    }
