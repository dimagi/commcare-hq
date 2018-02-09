from __future__ import absolute_import
from __future__ import unicode_literals
from decimal import Decimal

from corehq.apps.accounting.models import (
    FeatureType,
    SoftwarePlanEdition,
)

BOOTSTRAP_CONFIG = {
    (SoftwarePlanEdition.COMMUNITY, False, False): {
        'role': 'community_plan_v1',
        'product_rate_monthly_fee': Decimal('0.00'),
        'feature_rates': {
            FeatureType.USER: dict(monthly_limit=10, per_excess_fee=Decimal('2.00')),
            FeatureType.SMS: dict(monthly_limit=0),
        }
    },
    (SoftwarePlanEdition.STANDARD, False, False): {
        'role': 'standard_plan_v0',
        'product_rate_monthly_fee': Decimal('100.00'),
        'feature_rates': {
            FeatureType.USER: dict(monthly_limit=50, per_excess_fee=Decimal('2.00')),
            FeatureType.SMS: dict(monthly_limit=50),
        }
    },
    (SoftwarePlanEdition.PRO, False, False): {
        'role': 'pro_plan_v0',
        'product_rate_monthly_fee': Decimal('500.00'),
        'feature_rates': {
            FeatureType.USER: dict(monthly_limit=250, per_excess_fee=Decimal('2.00')),
            FeatureType.SMS: dict(monthly_limit=50),
        }
    },
    (SoftwarePlanEdition.ADVANCED, False, False): {
        'role': 'advanced_plan_v0',
        'product_rate_monthly_fee': Decimal('1000.00'),
        'feature_rates': {
            FeatureType.USER: dict(monthly_limit=500, per_excess_fee=Decimal('2.00')),
            FeatureType.SMS: dict(monthly_limit=50),
        }
    },
    (SoftwarePlanEdition.ADVANCED, True, False): {
        'role': 'advanced_plan_v0',
        'product_rate_monthly_fee': Decimal('0.00'),
        'feature_rates': {
            FeatureType.USER: dict(monthly_limit=10, per_excess_fee=Decimal('2.00')),
            FeatureType.SMS: dict(monthly_limit=0),
        }
    }
}
