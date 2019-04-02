# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations, models




class Migration(migrations.Migration):

    dependencies = [
        ('domain_migration_flags', '0001_initial'),
        ('tzmigration', '0001_initial')
    ]

    operations = [
        migrations.RunSQL(
            """
            INSERT INTO domain_migration_flags_domainmigrationprogress (domain, migration_slug, migration_status)
            SELECT domain, 'tzmigration' as migration_slug, migration_status
            FROM tzmigration_timezonemigrationprogress
            """,
            ""
        )
    ]
