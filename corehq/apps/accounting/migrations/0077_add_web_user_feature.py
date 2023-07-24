from django.db import migrations
from django.core.management import call_command

from corehq.privileges import LOADTEST_USERS
from corehq.util.django_migrations import skip_on_fresh_install

from corehq.apps.accounting.bootstrap.utils import _ensure_feature_rates
from corehq.apps.accounting.bootstrap.config.web_user_feature_rate import BOOTSTRAP_CONFIG


@skip_on_fresh_install
def _grandfather_basic_privs(apps, schema_editor):
    call_command('cchq_prbac_bootstrap')
    call_command(
        'cchq_prbac_grandfather_privs',
        LOADTEST_USERS,
        skip_edition='Paused,Community',
        noinput=True,
    )


def _add_web_user_feature(apps, schema_editor):
    Feature = apps.get_model('accounting', 'Feature')
    web_user_feature = Feature.objects.create(name='Web User', feature_type='Web User')
    features = [web_user_feature]
    feature_rates = _ensure_feature_rates(BOOTSTRAP_CONFIG['feature_rates'], features, None, True, apps)
    for feature_rate in feature_rates:
        feature_rate.save()


class Migration(migrations.Migration):
    dependencies = [
        ('accounting', '0076_location_owner_in_report_builder_priv'),
    ]

    operations = [
        migrations.RunPython(
            _grandfather_basic_privs,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RunPython(_add_web_user_feature, reverse_code=migrations.RunPython.noop),
    ]
