from decimal import Decimal

from corehq.apps.accounting.models import (
    FeatureType,
    SoftwarePlanEdition,
    UNLIMITED_FEATURE_USAGE,
)

BOOTSTRAP_CONFIG = {
    (SoftwarePlanEdition.ENTERPRISE, False, False): {
        'role': 'enterprise_plan_v0',
        'product_rate_monthly_fee': Decimal('0.00'),
        'feature_rates': {
            FeatureType.USER: dict(monthly_limit=UNLIMITED_FEATURE_USAGE, per_excess_fee=Decimal('0.00')),
            FeatureType.SMS: dict(monthly_limit=UNLIMITED_FEATURE_USAGE),
        }
    },
}
