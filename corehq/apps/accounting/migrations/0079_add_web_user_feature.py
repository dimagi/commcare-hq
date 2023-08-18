from django.db import migrations

from corehq.apps.accounting.bootstrap.utils import _ensure_feature_rates
from corehq.apps.accounting.bootstrap.config.web_user_feature_rate import BOOTSTRAP_CONFIG
from corehq.apps.accounting.models import FeatureType


def _add_web_user_feature(apps, schema_editor):
    Feature = apps.get_model('accounting', 'Feature')
    web_user_feature, _ = Feature.objects.get_or_create(name=FeatureType.WEB_USER, feature_type=FeatureType.WEB_USER)
    features = [web_user_feature]
    feature_rates = _ensure_feature_rates(BOOTSTRAP_CONFIG['feature_rates'], features, None, True, apps)
    for feature_rate in feature_rates:
        feature_rate.save()


def _remove_web_user_feature(apps, schema_editor):
    Feature = apps.get_model('accounting', 'Feature')
    FeatureRate = apps.get_model('accounting', 'FeatureRate')

    FeatureRate.objects.filter(feature__name=FeatureType.WEB_USER).delete()
    Feature.objects.filter(name=FeatureType.WEB_USER).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('accounting', '0078_revert_location_owner_in_report_builder_priv'),
    ]

    operations = [
        migrations.RunPython(_add_web_user_feature, reverse_code=_remove_web_user_feature),
    ]
