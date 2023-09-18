# Generated by Django 3.2.16 on 2023-04-25 10:25

import corehq.apps.es.migration_operations
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('es', '0002_add_tombstones'),
    ]

    operations = [
        corehq.apps.es.migration_operations.UpdateIndexMapping(
            name='hqusers_2017-09-07',
            type_='user',
            properties={
                'assigned_location_ids': {'type': 'string'},
                'domain_memberships': {'properties': {'assigned_location_ids': {'type': 'string'}}},
                'domain_membership': {'properties': {'assigned_location_ids': {'type': 'string'}}},
            },
            es_versions=[2],
        ),
    ]
