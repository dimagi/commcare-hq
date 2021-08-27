import sys

from django.db import migrations

from corehq.apps.accounting.models import BillingAccount
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def migrate_mirrors(apps, schema_editor):
    from corehq.apps.enterprise.models import EnterprisePermissions
    DomainPermissionsMirror = apps.get_model('users', 'DomainPermissionsMirror')
    sources = {o.source for o in DomainPermissionsMirror.objects.all()}
    for source in sources:
        account = BillingAccount.get_account_by_domain(source)
        account_domains = set(account.get_domains())
        mirror_domains = {o.mirror for o in DomainPermissionsMirror.objects.filter(source=source)}
        if EnterprisePermissions.objects.filter(account=account).exists():
            print(f"""
            Found a pre-existing enterprise permissions configuration for account {account.id}.
            Enterprise permissions no longer supports multiple configurations in the same account.
            Please delete one of the DomainPermissionsMirror source domains in this account.
            """)
            sys.exit(1)
        EnterprisePermissions(
            account=account,
            is_enabled=True,
            source_domain=source,
            domains=list(account_domains & mirror_domains - {source}),
        ).save()


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0027_role_permission_unique'),
        ('enterprise', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(migrate_mirrors, reverse_code=migrations.RunPython.noop, elidable=True),
    ]
