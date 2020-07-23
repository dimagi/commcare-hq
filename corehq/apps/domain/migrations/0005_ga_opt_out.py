from django.db import migrations, models

from corehq.apps.domain.models import Domain
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _disable_ga(apps, schema_editor):
    for domain in Domain.get_all():
        if domain.hipaa_compliant:
            domain.ga_opt_out = True
            domain.save()


class Migration(migrations.Migration):

    dependencies = [
        ('domain', '0004_domainauditrecordentry'),
    ]

    operations = [
        migrations.RunPython(_disable_ga, migrations.RunPython.noop)
    ]
