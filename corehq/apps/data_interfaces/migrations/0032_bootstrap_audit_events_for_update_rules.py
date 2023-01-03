from django.core.management import call_command
from django.db import migrations


def bootstrap_audit_events_for_automatic_update_rule(apps, schema_editor):
    call_command('bootstrap_field_audit_events',
                 'top-up',
                 ['AutomaticUpdateRule'])


def noop(*args, **kwargs):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('data_interfaces', '0031_add_domaincaserulerun_status_choices'),
        ('field_audit', '0002_add_is_bootstrap_column'),
    ]

    operations = [
        migrations.RunPython(bootstrap_audit_events_for_automatic_update_rule,
                             reverse_code=noop)
    ]
