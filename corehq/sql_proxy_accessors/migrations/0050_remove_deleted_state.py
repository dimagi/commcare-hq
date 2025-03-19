from django.conf import settings
from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('corehq', 'sql_proxy_accessors', 'sql_templates'), {
    'PL_PROXY_CLUSTER_NAME': settings.PL_PROXY_CLUSTER_NAME
})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_proxy_accessors', '0049_drop_unused_function'),
    ]

    operations = [
        migrator.get_migration('get_form_ids_for_user_2.sql'),
        migrator.get_migration('soft_delete_forms_3.sql'),
        migrator.get_migration('soft_undelete_forms_3.sql'),
    ]
