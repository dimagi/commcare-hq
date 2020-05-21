# -*- coding: utf-8 -*-
# Generated on 2020-05-19
from __future__ import unicode_literals

from django.db import migrations

from custom.icds_reports.utils.migrations import get_view_migrations


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0189_new_fields_to_bihar_demogrpahics'),
    ]

    operations = get_view_migrations()
