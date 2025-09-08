import corehq.apps.es.migration_operations
from corehq.apps.es.utils import index_runtime_name
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('es', '0016_add_new_index_for_cc_perf'),
    ]

    operations = [
        corehq.apps.es.migration_operations.UpdateIndexMapping(
            name=index_runtime_name('users-2024-05-09'),
            type_='user',
            properties={
                'is_account_confirmed': {'type': 'boolean'},
            },
            es_versions=[6],
        )
    ]
