from django.db import migrations

from corehq.apps.domain.models import Domain, EnableAllAddOnsSetting
from corehq.toggles import StaticToggle
from corehq.util.django_migrations import skip_on_fresh_install


def get_enabled_domains():
    """
    Returns the domains that have the ENABLE_ALL_ADD_ONS toggle enabled.
    """
    # Allows migration to be run after the toggle has been deleted
    toggle = StaticToggle('enable_all_add_ons', '', '')
    return toggle.get_enabled_domains()


@skip_on_fresh_install
def enable_all_add_ons(apps, schema_editor):
    """
    Set EnableAllAddOnsSetting.enabled for all domains with the
    ENABLE_ALL_ADD_ONS toggle enabled.
    """
    objs = [
        EnableAllAddOnsSetting(domain=d, enabled=True)
        for d in get_enabled_domains()
        if Domain.get_by_name(d)
    ]
    EnableAllAddOnsSetting.objects.bulk_create(objs, ignore_conflicts=True)


class Migration(migrations.Migration):
    dependencies = [
        ('domain', '0017_enablealladdonssetting'),
    ]

    operations = [
        migrations.RunPython(
            enable_all_add_ons,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
