import corehq.apps.es.migration_operations
from corehq.apps.es.utils import index_runtime_name
from corehq.apps.es.users import UserES, user_adapter
from django.db import migrations


def populate_user_domain_memberships(apps, schema_editor):
    user_ids = UserES().get_ids()

    for user in user_adapter.iter_docs(user_ids):
        memberships = []

        if user['doc_type'] == 'CommCareUser':
            membership = user['domain_membership']
            memberships.append(membership)
        elif user['doc_type'] == 'WebUser':
            for membership in user['domain_memberships']:
                memberships.append(membership)
        if memberships:
            user_adapter.update(
                user['_id'],
                {'user_domain_memberships': memberships},
                refresh=True
            )


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
            es_versions=[6]
        ),
        migrations.RunPython(
            populate_user_domain_memberships,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
