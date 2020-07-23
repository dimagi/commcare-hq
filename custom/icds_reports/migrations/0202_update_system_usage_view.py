# -*- coding: utf-8 -*-
# Generated on 2020-06-17
from __future__ import unicode_literals


from __future__ import unicode_literals

from django.db import migrations

from custom.icds_reports.utils.migrations import get_view_migrations


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0201_adding_version_agg_table'),
    ]

    operations = get_view_migrations()

