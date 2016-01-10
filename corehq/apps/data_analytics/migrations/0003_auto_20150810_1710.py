# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

from corehq.sql_db.operations import HqRunPython


def fill_in_user_type(apps, schema_editor):
    MALTRow = apps.get_model("data_analytics", "MALTRow")
    MALTRow.objects.filter(is_web_user=True).update(user_type="WebUser")
    MALTRow.objects.filter(is_web_user=False).update(user_type="CommCareUser")

def reverse_fill_in(apps, schema_editor):
    MALTRow = apps.get_model("data_analytics", "MALTRow")
    MALTRow.objects.filter(user_type="WebUser").update(is_web_user=True)
    MALTRow.objects.filter(user_type="CommCareUser").update(is_web_user=False)


class Migration(migrations.Migration):

    dependencies = [
        ('data_analytics', '0002_auto_20150810_1658'),
    ]

    operations = [
            HqRunPython(fill_in_user_type, reverse_fill_in),
    ]
