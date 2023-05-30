# -*- coding: utf-8 -*-
from django.db import migrations
from corehq.util.django_migrations import prompt_for_historical_migration, get_migration_name


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('fixtures', '0005_sqllookuptablemodels'),
    ]

    operations = [
        prompt_for_historical_migration(
            "fixtures", get_migration_name(__file__), "10f1b20a33ea07371e2b94c37e16ea81cfabcd53"),
    ]
