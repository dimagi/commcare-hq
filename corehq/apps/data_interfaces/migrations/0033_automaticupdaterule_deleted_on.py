from django.db import migrations, models

from corehq.apps.cleanup.utils import migrate_to_deleted_on
from corehq.apps.data_interfaces.models import AutomaticUpdateRule

INDEX_NAME = 'automaticupdaterule_deleted_on_idx'
TABLE_NAME = 'data_interfaces_automaticupdaterule'
COLUMNS = 'deleted_on'
WHERE_CLAUSE = 'deleted_on IS NOT NULL'
CREATE_INDEX = f"CREATE INDEX {INDEX_NAME} ON {TABLE_NAME} ({COLUMNS}) WHERE {WHERE_CLAUSE}"


def set_deleted_on_field(apps, schema_editor):
    migrate_to_deleted_on(AutomaticUpdateRule, 'deleted', should_audit=True)


class Migration(migrations.Migration):

    dependencies = [
        ('data_interfaces', '0032_bootstrap_audit_events_for_update_rules'),
    ]

    operations = [
        migrations.AddField(
            model_name='automaticupdaterule',
            name='deleted_on',
            field=models.DateTimeField(null=True),
        ),
        migrations.RunSQL(CREATE_INDEX),
        migrations.RunPython(set_deleted_on_field)
    ]
