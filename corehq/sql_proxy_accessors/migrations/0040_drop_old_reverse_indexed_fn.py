# Generated by Django 1.11.9 on 2018-01-30 19:04

from django.db import migrations




class Migration(migrations.Migration):

    dependencies = [
        ('sql_proxy_accessors', '0039_filter_get_reverse_indexed_cases'),
    ]

    operations = [
        migrations.RunSQL("DROP FUNCTION IF EXISTS get_reverse_indexed_cases(TEXT, TEXT[]);"),
    ]
