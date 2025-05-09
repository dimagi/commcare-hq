import corehq.apps.es.migration_operations
from corehq.apps.es.utils import index_runtime_name
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('es', '0014_enable_slowlogs'),
    ]

    operations = [
        corehq.apps.es.migration_operations.UpdateIndexMapping(
            name=index_runtime_name('users-2024-05-09'),
            type_='user',
            properties={
                'domain_memberships': {'properties': {'is_active': {'type': 'boolean'}}},
            },
            es_versions=[6],
        ),
    ]
