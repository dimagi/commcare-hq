# -*- coding: utf-8 -*-
# flake8: noqa
# Generated by Django 1.11.20 on 2019-04-05 17:47
from __future__ import absolute_import
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('translations', '0004_auto_20190318_1905'),
    ]

    operations = [
        migrations.AlterField(
            model_name='transifexblacklist',
            name='field_name',
            field=models.TextField(help_text="\nThis is the same string that appears in the bulk translations download.\nUsually the string in either case list or detail under 'property'.\nThis could be an xpath or case property name.\nIf it is an ID Mapping then the property should be '<property> (ID Mapping Text)'.\nFor the values each value should be '<id mapping value> (ID Mapping Value)'.\n<br>\nExample: case detail for tasks_type could have entries:\n<ul>\n    <li>tasks_type (ID Mapping Text)</li>\n    <li>child (ID Mapping Value)</li>\n    <li>pregnancy (ID Mapping Value)</li>\n</ul>\n"),
        ),
    ]
