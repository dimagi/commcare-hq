# -*- coding: utf-8 -*-

from django.db import migrations

from corehq.util.django_migrations import prompt_for_historical_migration, get_migration_name


class Migration(migrations.Migration):

    dependencies = [
        ('commtrack', '0004_update_overstock_threshold'),
    ]

    operations = [
        prompt_for_historical_migration(
            "commtrack", get_migration_name(__file__), "539a7399b995e03fd9ead14ca64a8e66b9b576a4")
    ]
