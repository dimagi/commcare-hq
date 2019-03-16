# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations




class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0043_faster_get_reverse_indexed_cases'),
    ]

    operations = [
        migrations.RunSQL("DROP FUNCTION IF EXISTS get_case_types_for_domain(TEXT)")
    ]
