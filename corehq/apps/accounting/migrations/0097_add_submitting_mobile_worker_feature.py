from django.db import migrations

from corehq.apps.accounting.bootstrap.config.submitting_mobile_worker_feature_rate import (
    BOOTSTRAP_CONFIG,
)
from corehq.apps.accounting.bootstrap.utils import _ensure_feature_rates
from corehq.apps.accounting.models import FeatureType


def _add_submitting_mobile_worker_feature(apps, schema_editor):
    Feature = apps.get_model('accounting', 'Feature')
    submitting_mobile_worker_feature, _ = Feature.objects.get_or_create(
        name=FeatureType.SUBMITTING_MOBILE_WORKER,
        feature_type=FeatureType.SUBMITTING_MOBILE_WORKER
    )
    features = [submitting_mobile_worker_feature]
    feature_rates = _ensure_feature_rates(BOOTSTRAP_CONFIG['feature_rates'], features, None, True, apps)
    for feature_rate in feature_rates:
        feature_rate.save()


def _remove_submitting_mobile_worker_feature(apps, schema_editor):
    Feature = apps.get_model('accounting', 'Feature')
    FeatureRate = apps.get_model('accounting', 'FeatureRate')

    FeatureRate.objects.filter(feature__name=FeatureType.SUBMITTING_MOBILE_WORKER).delete()
    Feature.objects.filter(name=FeatureType.SUBMITTING_MOBILE_WORKER).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounting", "0096_domainsubmittingmobileworkerhistory_and_featuretype_choice"),
    ]

    operations = [
        migrations.RunPython(
            _add_submitting_mobile_worker_feature,
            reverse_code=_remove_submitting_mobile_worker_feature
        ),
    ]
