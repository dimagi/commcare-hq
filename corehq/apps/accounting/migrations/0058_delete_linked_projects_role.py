from django.db import migrations
from django.core.management import call_command
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _revoke_linked_project_priv(apps, schema_editor):
    call_command(
        'cchq_prbac_revoke_privs',
        'linked_projects',
        delete_privs=True,
        check_privs_exist=False,
        noinput=True,
    )


class Migration(migrations.Migration):
    dependencies = [
        ('accounting', '0057_add_sms_report_toggle'),
    ]

    operations = [
        migrations.RunPython(_revoke_linked_project_priv),
    ]
