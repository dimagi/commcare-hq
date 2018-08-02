from __future__ import unicode_literals
from __future__ import absolute_import

from django.conf import settings
from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('corehq', 'sql_proxy_accessors', 'sql_templates'), {
    'PL_PROXY_CLUSTER_NAME': settings.PL_PROXY_CLUSTER_NAME
})


class Migration(migrations.Migration):

    dependencies = [
        ('sql_proxy_accessors', '0042_case_attachment_drops'),
        ('form_processor', '0073_casetransaction__client_date'),
    ]

    operations = [
        migrator.get_migration('compare_server_client_case_transaction_order.sql'),
    ]
