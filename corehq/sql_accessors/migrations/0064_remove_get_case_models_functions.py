# -*- coding: utf-8 -*-
from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0063_get_ledger_values_for_cases_2'),
    ]

    operations = [
        migrations.RunSQL('DROP FUNCTION IF EXISTS get_case_transactions(TEXT)'),
        migrations.RunSQL('DROP FUNCTION IF EXISTS get_case_attachments(TEXT)'),
        migrations.RunSQL('DROP FUNCTION IF EXISTS get_case_by_id(TEXT)'),
        migrations.RunSQL('DROP FUNCTION IF EXISTS check_form_exists(TEXT, TEXT)'),
        migrations.RunSQL('DROP FUNCTION IF EXISTS get_case_indices(TEXT, TEXT)'),
        migrations.RunSQL('DROP FUNCTION IF EXISTS get_form_attachments(TEXT)'),
        migrations.RunSQL('DROP FUNCTION IF EXISTS get_form_operations(TEXT)'),
    ]
