from decimal import Decimal

from corehq.apps.accounting.models import FeatureType, SoftwarePlanEdition

BOOTSTRAP_CONFIG = {
    # pay monthly
    (SoftwarePlanEdition.STANDARD, False, False, False): {
        'role': 'standard_plan_v2',
        'product_rate_monthly_fee': Decimal('120.00'),
        'feature_rates': {
            FeatureType.USER: dict(monthly_limit=50, per_excess_fee=Decimal('2.00')),
            FeatureType.SMS: dict(monthly_limit=0),
        }
    },
    # pay annually
    (SoftwarePlanEdition.STANDARD, False, False, True): {
        'role': 'standard_plan_v2',
        'product_rate_monthly_fee': Decimal('100.00'),
        'feature_rates': {
            FeatureType.USER: dict(monthly_limit=50, per_excess_fee=Decimal('2.00')),
            FeatureType.SMS: dict(monthly_limit=0),
        }
    },
}
