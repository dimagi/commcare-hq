from django.db import migrations

from corehq.apps.cloudcare.models import ApplicationAccess
from corehq.toggles import NAMESPACE_DOMAIN, WEB_APPS_PERMISSIONS_VIA_GROUPS
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def enable_flag(apps, schema_editor):
    for access in ApplicationAccess.objects.filter(restrict=True):
        WEB_APPS_PERMISSIONS_VIA_GROUPS.set(access.domain, enabled=True, namespace=NAMESPACE_DOMAIN)


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0061_auto_20240423_0802'),
    ]

    operations = [
        migrations.RunPython(enable_flag, migrations.RunPython.noop),
    ]
