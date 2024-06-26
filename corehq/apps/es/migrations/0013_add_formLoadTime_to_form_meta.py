# Generated by Django 4.2.11 on 2024-06-25 14:36

import corehq.apps.es.migration_operations
from django.db import migrations

from corehq.apps.es.utils import index_runtime_name


class Migration(migrations.Migration):

    dependencies = [
        ('es', '0012_add_new_index_for_bha'),
    ]

    operations = [
        corehq.apps.es.migration_operations.UpdateIndexMapping(
            name=index_runtime_name('forms-20230524'),
            type_='xform',
            properties={
                'form': {'dynamic': False, 'properties': {'#type': {'type': 'keyword'}, '@name': {'type': 'keyword'}, 'case': {'dynamic': False, 'properties': {'@case_id': {'type': 'keyword'}, '@date_modified': {'format': "epoch_millis||yyyy-MM-dd||yyyy-MM-dd'T'HH:mm:ssZZ||yyyy-MM-dd'T'HH:mm:ss.SSSSSS||yyyy-MM-dd'T'HH:mm:ss.SSSSSS'Z'||yyyy-MM-dd'T'HH:mm:ss'Z'||yyyy-MM-dd'T'HH:mm:ssZ||yyyy-MM-dd'T'HH:mm:ssZZ'Z'||yyyy-MM-dd'T'HH:mm:ss.SSSZZ||yyyy-MM-dd'T'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss.SSSSSS||mm/dd/yy' 'HH:mm:ss", 'type': 'date'}, '@user_id': {'type': 'keyword'}, '@xmlns': {'type': 'keyword'}, 'case_id': {'type': 'keyword'}, 'date_modified': {'format': "epoch_millis||yyyy-MM-dd||yyyy-MM-dd'T'HH:mm:ssZZ||yyyy-MM-dd'T'HH:mm:ss.SSSSSS||yyyy-MM-dd'T'HH:mm:ss.SSSSSS'Z'||yyyy-MM-dd'T'HH:mm:ss'Z'||yyyy-MM-dd'T'HH:mm:ssZ||yyyy-MM-dd'T'HH:mm:ssZZ'Z'||yyyy-MM-dd'T'HH:mm:ss.SSSZZ||yyyy-MM-dd'T'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss.SSSSSS||mm/dd/yy' 'HH:mm:ss", 'type': 'date'}, 'user_id': {'type': 'keyword'}, 'xmlns': {'type': 'keyword'}}}, 'meta': {'dynamic': False, 'properties': {'appVersion': {'type': 'keyword'}, 'app_build_version': {'type': 'keyword'}, 'commcare_version': {'type': 'keyword'}, 'deviceID': {'type': 'keyword'}, 'formLoadTime': {'type': 'keyword'}, 'geo_point': {'type': 'geo_point'}, 'instanceID': {'type': 'keyword'}, 'timeEnd': {'format': "epoch_millis||yyyy-MM-dd||yyyy-MM-dd'T'HH:mm:ssZZ||yyyy-MM-dd'T'HH:mm:ss.SSSSSS||yyyy-MM-dd'T'HH:mm:ss.SSSSSS'Z'||yyyy-MM-dd'T'HH:mm:ss'Z'||yyyy-MM-dd'T'HH:mm:ssZ||yyyy-MM-dd'T'HH:mm:ssZZ'Z'||yyyy-MM-dd'T'HH:mm:ss.SSSZZ||yyyy-MM-dd'T'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss.SSSSSS||mm/dd/yy' 'HH:mm:ss", 'type': 'date'}, 'timeStart': {'format': "epoch_millis||yyyy-MM-dd||yyyy-MM-dd'T'HH:mm:ssZZ||yyyy-MM-dd'T'HH:mm:ss.SSSSSS||yyyy-MM-dd'T'HH:mm:ss.SSSSSS'Z'||yyyy-MM-dd'T'HH:mm:ss'Z'||yyyy-MM-dd'T'HH:mm:ssZ||yyyy-MM-dd'T'HH:mm:ssZZ'Z'||yyyy-MM-dd'T'HH:mm:ss.SSSZZ||yyyy-MM-dd'T'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss.SSSSSS||mm/dd/yy' 'HH:mm:ss", 'type': 'date'}, 'userID': {'null_value': '__NULL__', 'type': 'keyword'}, 'username': {'type': 'keyword'}}}}},
            },
            es_versions=[5],
        ),
    ]
