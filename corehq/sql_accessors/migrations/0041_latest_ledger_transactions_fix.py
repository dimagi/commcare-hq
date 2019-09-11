from django.db import migrations

from corehq.form_processor.models import XFormInstanceSQL
from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'))


class Migration(migrations.Migration):

    dependencies = [
        ('sql_accessors', '0040_fix_case_reindex_query'),
    ]

    operations = [
        migrator.get_migration('get_latest_ledger_transaction.sql'),
    ]
