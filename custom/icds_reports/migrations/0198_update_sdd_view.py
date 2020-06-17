# -*- coding: utf-8 -*-
# Generated on 2020-04-28
from __future__ import unicode_literals


from __future__ import unicode_literals

from django.db import migrations

from custom.icds_reports.utils.migrations import get_view_migrations


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0197_update_system_usage_report_view'),
    ]

    operations = get_view_migrations()
