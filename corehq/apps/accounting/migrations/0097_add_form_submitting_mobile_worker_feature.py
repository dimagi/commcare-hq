from django.db import migrations

from corehq.apps.accounting.bootstrap.config.form_submitting_mobile_worker_feature_rate import (
    BOOTSTRAP_CONFIG,
)
from corehq.apps.accounting.bootstrap.utils import ensure_feature_rates
from corehq.apps.accounting.models import FeatureType


def _add_form_submitting_mobile_worker_feature(apps, schema_editor):
    Feature = apps.get_model('accounting', 'Feature')
    form_submitting_mobile_worker_feature, _ = Feature.objects.get_or_create(
        name=FeatureType.FORM_SUBMITTING_MOBILE_WORKER,
        feature_type=FeatureType.FORM_SUBMITTING_MOBILE_WORKER
    )
    features = [form_submitting_mobile_worker_feature]
    feature_rates = ensure_feature_rates(BOOTSTRAP_CONFIG['feature_rates'], features, True, apps)
    for feature_rate in feature_rates:
        feature_rate.save()


def _remove_form_submitting_mobile_worker_feature(apps, schema_editor):
    Feature = apps.get_model('accounting', 'Feature')
    FeatureRate = apps.get_model('accounting', 'FeatureRate')

    FeatureRate.objects.filter(feature__name=FeatureType.FORM_SUBMITTING_MOBILE_WORKER).delete()
    Feature.objects.filter(name=FeatureType.FORM_SUBMITTING_MOBILE_WORKER).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounting", "0096_formsubmittingmobileworkerhistory_and_featuretype_choice"),
    ]

    operations = [
        migrations.RunPython(
            _add_form_submitting_mobile_worker_feature,
            reverse_code=_remove_form_submitting_mobile_worker_feature
        ),
    ]
