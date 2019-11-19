from decimal import Decimal

from corehq.apps.accounting.models import FeatureType, SoftwarePlanEdition

BOOTSTRAP_CONFIG = {
    (SoftwarePlanEdition.PRO, False, False): {
        'role': 'pro_plan_v1',
        'product_rate_monthly_fee': Decimal('600.00'),
        'feature_rates': {
            FeatureType.USER: dict(monthly_limit=250, per_excess_fee=Decimal('2.00')),
            FeatureType.SMS: dict(monthly_limit=50),
        },
    },
}
