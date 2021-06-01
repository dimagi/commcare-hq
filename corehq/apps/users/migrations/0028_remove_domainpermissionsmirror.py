from django.db import migrations

from corehq.apps.accounting.models import BillingAccount
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def migrate_mirrors(apps, schema_editor):
    DomainPermissionsMirror = apps.get_model('users', 'DomainPermissionsMirror')
    sources = {o.source for o in DomainPermissionsMirror.objects.all()}
    for source in sources:
        account = BillingAccount.get_account_by_domain(source)
        account.permissions_source_domain = source
        all_domains = set(account.get_domains())
        mirror_domains = {o.mirror for o in DomainPermissionsMirror.objects.filter(source=source)}
        account.permissions_ignore_domains = list(all_domains - mirror_domains)
        account.save()


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0027_role_permission_unique'),
        ('accounting', '0055_enterprise_permissions'),
    ]

    operations = [
        migrations.RunPython(migrate_mirrors, reverse_code=migrations.RunPython.noop, elidable=True),
        # TODO: delete table
    ]
