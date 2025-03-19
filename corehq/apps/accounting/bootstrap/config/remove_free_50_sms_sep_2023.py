from decimal import Decimal

from corehq.apps.accounting.models import FeatureType, SoftwarePlanEdition

BOOTSTRAP_CONFIG = {
    (SoftwarePlanEdition.STANDARD, False, False): {
        'role': 'standard_plan_v1',
        'product_rate_monthly_fee': Decimal('300.00'),
        'feature_rates': {
            FeatureType.USER: dict(monthly_limit=125, per_excess_fee=Decimal('2.00')),
            FeatureType.SMS: dict(monthly_limit=0),
        },
    },
    (SoftwarePlanEdition.PRO, False, False): {
        'role': 'pro_plan_v1',
        'product_rate_monthly_fee': Decimal('600.00'),
        'feature_rates': {
            FeatureType.USER: dict(monthly_limit=250, per_excess_fee=Decimal('2.00')),
            FeatureType.SMS: dict(monthly_limit=0),
        },
    },
    (SoftwarePlanEdition.ADVANCED, False, False): {
        'role': 'advanced_plan_v0',
        'product_rate_monthly_fee': Decimal('1200.00'),
        'feature_rates': {
            FeatureType.USER: dict(monthly_limit=500, per_excess_fee=Decimal('2.00')),
            FeatureType.SMS: dict(monthly_limit=0),
        }
    },
}
