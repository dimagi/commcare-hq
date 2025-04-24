
import corehq.apps.es.migration_operations
from corehq.apps.es.utils import index_runtime_name
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('es', '0012_add_new_index_for_bha'),
    ]

    operations = [
        corehq.apps.es.migration_operations.UpdateIndexMapping(
            name=index_runtime_name('users-2024-05-09'),
            type_='user',
            properties={
                'last_modified': {
                    'type': 'date',
                    'format': "yyyy-MM-dd||yyyy-MM-dd'T'HH:mm:ssZZ||yyyy-MM-dd'T'HH:mm:ss.SSSSSS||yyyy-MM-dd'T'HH:mm:ss.SSSSSS'Z'||yyyy-MM-dd'T'HH:mm:ss'Z'||yyyy-MM-dd'T'HH:mm:ssZ||yyyy-MM-dd'T'HH:mm:ssZZ'Z'||yyyy-MM-dd'T'HH:mm:ss.SSSZZ||yyyy-MM-dd'T'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss.SSSSSS||mm/dd/yy' 'HH:mm:ss"
                },
            },
            es_versions=[5],
        ),
    ]
