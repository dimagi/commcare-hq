# -*- coding: utf-8 -*-
# Generated on 2020-05-19
from __future__ import unicode_literals

from django.db import migrations

from custom.icds_reports.utils.migrations import get_view_migrations


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0194_auto_20200528_1024'),
    ]

    operations = get_view_migrations()
