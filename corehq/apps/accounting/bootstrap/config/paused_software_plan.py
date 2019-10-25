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
}
