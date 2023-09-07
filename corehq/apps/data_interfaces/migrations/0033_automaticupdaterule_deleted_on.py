from django.db import migrations, models

from corehq.apps.cleanup.utils import migrate_to_deleted_on
from corehq.apps.data_interfaces.models import AutomaticUpdateRule


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
        migrations.AddIndex(
            model_name='automaticupdaterule',
            index=models.Index(
                condition=models.Q(('deleted_on__isnull', False)),
                fields=['deleted_on'], name='data_interfaces_a_7200b513_idx'),
        ),
        migrations.RunPython(set_deleted_on_field),
    ]
