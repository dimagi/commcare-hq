# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

from django.db import migrations

from custom.icds_reports.utils.migrations import (
    get_composite_primary_key_migrations,
)


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0117_awc_location_local'),
    ]

    operations = get_composite_primary_key_migrations([
        'ccsrecordmonthly',
        'childhealthmonthly',
    ])
