from decimal import Decimal

from corehq.apps.accounting.models import FeatureType, SoftwarePlanEdition

BOOTSTRAP_CONFIG = {
    (SoftwarePlanEdition.PAUSED, False, False): {
        'role': 'paused_plan_v0',
        'product_rate_monthly_fee': Decimal('0.00'),
        'feature_rates': {
            FeatureType.USER: dict(monthly_limit=0, per_excess_fee=Decimal('0.00')),
            FeatureType.SMS: dict(monthly_limit=0),
        }
    },
    (SoftwarePlanEdition.FREE, False, False): {
        'role': 'community_plan_v2',
        'product_rate_monthly_fee': Decimal('0.00'),
        'feature_rates': {
            FeatureType.USER: dict(monthly_limit=5, per_excess_fee=Decimal('2.00')),
            FeatureType.SMS: dict(monthly_limit=0),
        }
    },
    (SoftwarePlanEdition.STANDARD, False, False): {
        'role': 'standard_plan_v1',
        'product_rate_monthly_fee': Decimal('300.00'),
        'feature_rates': {
            FeatureType.USER: dict(monthly_limit=125, per_excess_fee=Decimal('2.00')),
            FeatureType.SMS: dict(monthly_limit=50),
        },
    },
    (SoftwarePlanEdition.PRO, False, False): {
        'role': 'pro_plan_v1',
        'product_rate_monthly_fee': Decimal('600.00'),
        'feature_rates': {
            FeatureType.USER: dict(monthly_limit=250, per_excess_fee=Decimal('2.00')),
            FeatureType.SMS: dict(monthly_limit=50),
        },
    },
}
