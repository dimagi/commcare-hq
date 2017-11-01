from __future__ import absolute_import
from decimal import Decimal

from corehq.apps.accounting.models import (
    FeatureType,
    SoftwarePlanEdition,
)

BOOTSTRAP_CONFIG = {
    (SoftwarePlanEdition.STANDARD, False, True): {
        'role': 'standard_plan_report_builder_v0',
        'product_rate_monthly_fee': Decimal('100.00'),
        'feature_rates': {
            FeatureType.USER: dict(monthly_limit=50, per_excess_fee=Decimal('2.00')),
            FeatureType.SMS: dict(monthly_limit=50),
        }
    },
    (SoftwarePlanEdition.PRO, False, True): {
        'role': 'pro_plan_report_builder_v0',
        'product_rate_monthly_fee': Decimal('500.00'),
        'feature_rates': {
            FeatureType.USER: dict(monthly_limit=250, per_excess_fee=Decimal('2.00')),
            FeatureType.SMS: dict(monthly_limit=50),
        }
    },
    (SoftwarePlanEdition.ADVANCED, False, True): {
        'role': 'advanced_plan_report_builder_v0',
        'product_rate_monthly_fee': Decimal('1000.00'),
        'feature_rates': {
            FeatureType.USER: dict(monthly_limit=500, per_excess_fee=Decimal('2.00')),
            FeatureType.SMS: dict(monthly_limit=50),
        }
    },
}
