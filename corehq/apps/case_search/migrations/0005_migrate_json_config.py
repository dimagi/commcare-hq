# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2017-05-18 19:39
from __future__ import unicode_literals

from collections import defaultdict
from corehq.sql_db.operations import HqRunPython
from django.db import migrations


def migrate_json_config_to_model(apps, schema_editor):
    CaseSearchConfig = apps.get_model('case_search', 'CaseSearchConfig')
    FuzzyProperties = apps.get_model('case_search', 'FuzzyProperties')
    for config in CaseSearchConfig.objects.all():
        config_json = config._config
        old_fuzzy_properties = config_json.get('fuzzy_properties', [])
        old_fuzzy_properties_by_casetype = defaultdict(list)
        for old_fuzzy_property in old_fuzzy_properties:
            for p in old_fuzzy_property['properties']:
                old_fuzzy_properties_by_casetype[old_fuzzy_property['case_type']].append(p)

        for case_type, fuzzy_properties in old_fuzzy_properties_by_casetype.iteritems():
            new_fuzzy_properties = FuzzyProperties(
                domain=config.domain,
                case_type=case_type,
                properties=fuzzy_properties
            )
            new_fuzzy_properties.save()
            config.fuzzy_properties.add(new_fuzzy_properties)
            config.save()


class Migration(migrations.Migration):

    dependencies = [
        ('case_search', '0004_auto_20170518_2018'),
    ]

    operations = [
        HqRunPython(migrate_json_config_to_model)
    ]
