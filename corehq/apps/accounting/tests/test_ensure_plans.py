from __future__ import absolute_import
from __future__ import unicode_literals

from decimal import Decimal
import six

from django.apps import apps

from corehq.apps.accounting.bootstrap.config.testing import BOOTSTRAP_CONFIG_TESTING
from corehq.apps.accounting.bootstrap.utils import ensure_plans
from corehq.apps.accounting.models import (
    DefaultProductPlan,
    FeatureType,
    SoftwarePlanEdition,
    UNLIMITED_FEATURE_USAGE,
)
from corehq.apps.accounting.tests.base_tests import BaseAccountingTest
from corehq.apps.accounting.utils import clear_plan_version_cache


class TestEnsurePlans(BaseAccountingTest):

    def tearDown(self):
        clear_plan_version_cache()
        super(TestEnsurePlans, self).tearDown()

    def test_ensure_plans(self):
        self._test_plan_versions_ensured(BOOTSTRAP_CONFIG_TESTING)
        self._test_plan_versions_ensured({
            (SoftwarePlanEdition.COMMUNITY, False, False): {
                'role': 'community_plan_v1',
                'product_rate_monthly_fee': Decimal('0.00'),
                'feature_rates': {
                    FeatureType.USER: dict(monthly_limit=12, per_excess_fee=Decimal('1.01')),
                    FeatureType.SMS: dict(monthly_limit=0),
                }
            },
            (SoftwarePlanEdition.STANDARD, False, False): {
                'role': 'standard_plan_v0',
                'product_rate_monthly_fee': Decimal('301.00'),
                'feature_rates': {
                    FeatureType.USER: dict(monthly_limit=14, per_excess_fee=Decimal('1.01')),
                    FeatureType.SMS: dict(monthly_limit=13),
                }
            },
            (SoftwarePlanEdition.PRO, False, False): {
                'role': 'pro_plan_v0',
                'product_rate_monthly_fee': Decimal('601.00'),
                'feature_rates': {
                    FeatureType.USER: dict(monthly_limit=16, per_excess_fee=Decimal('1.01')),
                    FeatureType.SMS: dict(monthly_limit=15),
                }
            },
            (SoftwarePlanEdition.ADVANCED, False, False): {
                'role': 'advanced_plan_v0',
                'product_rate_monthly_fee': Decimal('1201.00'),
                'feature_rates': {
                    FeatureType.USER: dict(monthly_limit=18, per_excess_fee=Decimal('1.01')),
                    FeatureType.SMS: dict(monthly_limit=17),
                }
            },
            (SoftwarePlanEdition.ADVANCED, True, False): {
                'role': 'advanced_plan_v0',
                'product_rate_monthly_fee': Decimal('0.00'),
                'feature_rates': {
                    FeatureType.USER: dict(monthly_limit=12, per_excess_fee=Decimal('1.01')),
                    FeatureType.SMS: dict(monthly_limit=0),
                }
            },
            (SoftwarePlanEdition.ENTERPRISE, False, False): {
                'role': 'enterprise_plan_v0',
                'product_rate_monthly_fee': Decimal('0.00'),
                'feature_rates': {
                    FeatureType.USER: dict(monthly_limit=UNLIMITED_FEATURE_USAGE, per_excess_fee=Decimal('0.00')),
                    FeatureType.SMS: dict(monthly_limit=UNLIMITED_FEATURE_USAGE),
                }
            },
        })

    def _test_plan_versions_ensured(self, bootstrap_config):
        ensure_plans(bootstrap_config, True, apps)
        for (edition, is_trial, has_report_builder), config in six.iteritems(bootstrap_config):
            software_plan_version = DefaultProductPlan.get_default_plan_version(
                edition=edition, is_trial=is_trial, is_report_builder_enabled=has_report_builder
            )

            self.assertEqual(software_plan_version.role.slug, config['role'])

            self.assertEqual(software_plan_version.product_rate.monthly_fee, config['product_rate_monthly_fee'])

            self.assertEqual(
                software_plan_version.user_limit,
                config['feature_rates'][FeatureType.USER]['monthly_limit']
            )
            self.assertEqual(
                software_plan_version.user_feature.per_excess_fee,
                config['feature_rates'][FeatureType.USER]['per_excess_fee']
            )

            sms_feature_rate = software_plan_version.feature_rates.get(feature__feature_type=FeatureType.SMS)
            self.assertEqual(
                sms_feature_rate.monthly_limit,
                config['feature_rates'][FeatureType.SMS]['monthly_limit']
            )
            self.assertEqual(sms_feature_rate.per_excess_fee, 0)
