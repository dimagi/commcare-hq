from django.db import migrations

from django_prbac.models import Role
from corehq.util.django_migrations import skip_on_fresh_install
from corehq.toggles import (
    SHOW_OWNER_LOCATION_PROPERTY_IN_REPORT_BUILDER,
    SHOW_OWNER_LOCATION_PROPERTY_IN_REPORT_BUILDER_TOGGLE,
    NAMESPACE_DOMAIN,
)
from corehq import privileges

PRIVILEGE = privileges.SHOW_OWNER_LOCATION_PROPERTY_IN_REPORT_BUILDER
FROZEN_TOGGLE = SHOW_OWNER_LOCATION_PROPERTY_IN_REPORT_BUILDER
NEW_TOGGLE = SHOW_OWNER_LOCATION_PROPERTY_IN_REPORT_BUILDER_TOGGLE


@skip_on_fresh_install
def _give_grandfathered_domains_ff_access(apps, schema_editor):
    # Make sure all grandfathered domains have the new toggle enabled
    for domain in FROZEN_TOGGLE.get_enabled_domains():
        NEW_TOGGLE.set(
            domain,
            True,
            NAMESPACE_DOMAIN,
        )
    # Remove the Role
    try:
        role = Role.objects.get(slug=PRIVILEGE)
        role.delete()
    except Role.DoesNotExist:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0077_case_list_explorer_priv'),
    ]

    operations = [
        migrations.RunPython(
            _give_grandfathered_domains_ff_access,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
