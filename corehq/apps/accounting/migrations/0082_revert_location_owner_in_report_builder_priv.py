from django.db import migrations

from django_prbac.models import Role
from corehq.util.django_migrations import skip_on_fresh_install
from corehq import privileges


@skip_on_fresh_install
def _remove_role_from_feature_plan(apps, schema_editor):
    try:
        role = Role.objects.get(slug=privileges.SHOW_OWNER_LOCATION_PROPERTY_IN_REPORT_BUILDER)
        role.delete()
    except Role.DoesNotExist:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0081_billingaccount_bill_web_user'),
    ]

    operations = [
        migrations.RunPython(
            _remove_role_from_feature_plan,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
