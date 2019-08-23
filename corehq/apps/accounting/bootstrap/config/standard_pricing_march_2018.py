from decimal import Decimal

from corehq.apps.accounting.models import (
    FeatureType,
    SoftwarePlanEdition,
)

BOOTSTRAP_CONFIG = {
    (SoftwarePlanEdition.STANDARD, False, False): {
        'role': 'standard_plan_v0',
        'product_rate_monthly_fee': Decimal('250.00'),
        'feature_rates': {
            FeatureType.USER: dict(monthly_limit=50, per_excess_fee=Decimal('2.00')),
            FeatureType.SMS: dict(monthly_limit=50),
        }
    },
}
