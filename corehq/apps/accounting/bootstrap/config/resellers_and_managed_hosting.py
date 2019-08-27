from decimal import Decimal

from corehq.apps.accounting.models import FeatureType, SoftwarePlanEdition

BOOTSTRAP_CONFIG = {
    (SoftwarePlanEdition.MANAGED_HOSTING, False, False): {
        'role': 'advanced_plan_v0',
        'product_rate_monthly_fee': Decimal('1000.00'),
        'feature_rates': {
            FeatureType.USER: dict(monthly_limit=0, per_excess_fee=Decimal('1.00')),
            FeatureType.SMS: dict(monthly_limit=0),
        }
    },
    (SoftwarePlanEdition.RESELLER, False, False): {
        'role': 'advanced_plan_v0',
        'product_rate_monthly_fee': Decimal('1000.00'),
        'feature_rates': {
            FeatureType.USER: dict(monthly_limit=10, per_excess_fee=Decimal('1.00')),
            FeatureType.SMS: dict(monthly_limit=0),
        }
    },
}
