# -*- coding: utf-8 -*-

from django.db import migrations




class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0044_remove_get_case_types_for_domain'),
    ]

    operations = [
        migrations.RunSQL("DROP FUNCTION IF EXISTS case_modified_since(TEXT, TIMESTAMP)")
    ]
