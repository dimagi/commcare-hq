from django.db import migrations

from corehq.apps.domain.models import Domain
from corehq.util.django_migrations import skip_on_fresh_install

from corehq.toggles import RESTRICT_MOBILE_ACCESS


@skip_on_fresh_install
def _enable_restrict_mobile_access(apps, schema_editor):
    for domain in RESTRICT_MOBILE_ACCESS.get_enabled_domains():
        domain_obj = Domain.get_by_name(domain)
        if domain_obj and not domain_obj.restrict_mobile_access:
            domain_obj.restrict_mobile_access = True
            domain_obj.save()


class Migration(migrations.Migration):

    dependencies = [
        ('domain', '0008_use_livequery'),
    ]

    operations = [
        migrations.RunPython(_enable_restrict_mobile_access, migrations.RunPython.noop)
    ]
