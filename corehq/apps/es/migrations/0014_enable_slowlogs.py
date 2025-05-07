from django.db import migrations

from corehq.apps.es.client import manager
from corehq.apps.es.transient_util import iter_doc_adapters
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _configure_slowlogs(apps, schema_editor):
    for adapter in iter_doc_adapters():
        manager.index_configure_for_standard_ops(adapter.index_name)


class Migration(migrations.Migration):
    dependencies = [
        ('es', '0013_add_last_modifed'),
    ]

    operations = [migrations.RunPython(_configure_slowlogs, reverse_code=migrations.RunPython.noop)]
