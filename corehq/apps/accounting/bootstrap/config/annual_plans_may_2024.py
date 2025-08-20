from decimal import Decimal

from corehq.apps.accounting.models import FeatureType, SoftwarePlanEdition

BOOTSTRAP_CONFIG = {
    (SoftwarePlanEdition.STANDARD, False, False, True): {
        'role': 'standard_plan_v1',
        'product_rate_monthly_fee': Decimal('250.00'),
        'feature_rates': {
            FeatureType.USER: dict(monthly_limit=125, per_excess_fee=Decimal('2.00')),
            FeatureType.SMS: dict(monthly_limit=0),
        },
    },
    (SoftwarePlanEdition.PRO, False, False, True): {
        'role': 'pro_plan_v1',
        'product_rate_monthly_fee': Decimal('500.00'),
        'feature_rates': {
            FeatureType.USER: dict(monthly_limit=250, per_excess_fee=Decimal('2.00')),
            FeatureType.SMS: dict(monthly_limit=0),
        },
    },
    (SoftwarePlanEdition.ADVANCED, False, False, True): {
        'role': 'advanced_plan_v0',
        'product_rate_monthly_fee': Decimal('1000.00'),
        'feature_rates': {
            FeatureType.USER: dict(monthly_limit=500, per_excess_fee=Decimal('2.00')),
            FeatureType.SMS: dict(monthly_limit=0),
        }
    },
}
