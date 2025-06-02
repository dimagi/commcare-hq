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
                'user_domain_memberships': {'dynamic': False, 'properties': {'assigned_location_ids': {'type': 'keyword'}, 'doc_type': {'type': 'keyword'}, 'domain': {'fields': {'exact': {'type': 'keyword'}}, 'type': 'text'}, 'is_active': {'type': 'boolean'}, 'is_admin': {'type': 'boolean'}, 'location_id': {'type': 'keyword'}, 'override_global_tz': {'type': 'boolean'}, 'role_id': {'type': 'keyword'}, 'timezone': {'type': 'text'}}, 'type': 'nested'},
            },
            es_versions=[6],
        )
    ]
