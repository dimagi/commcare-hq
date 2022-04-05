from django.db import migrations

from ..utils import get_all_expected_es_indices, update_mapping_migration_op


class Migration(migrations.Migration):

    dependencies = []

    operations = [
        update_mapping_migration_op(info) for info in get_all_expected_es_indices()
    ]
