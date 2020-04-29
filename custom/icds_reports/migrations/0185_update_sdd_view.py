# -*- coding: utf-8 -*-
# Generated on 2020-04-28
from __future__ import unicode_literals


from __future__ import unicode_literals

from django.db import migrations, models

from custom.icds_reports.utils.migrations import get_view_migrations


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0179_location_deprecation_columns'),
    ]

    operations = []

    operations.extend(get_view_migrations())
