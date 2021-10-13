# -*- coding: utf-8 -*-

from django.db import migrations

from corehq.util.django_migrations import block_upgrade_for_removed_migration


class Migration(migrations.Migration):

    dependencies = [
        ('commtrack', '0004_update_overstock_threshold'),
    ]

    operations = [
        block_upgrade_for_removed_migration("539a7399b995e03fd9ead14ca64a8e66b9b576a4")
    ]
