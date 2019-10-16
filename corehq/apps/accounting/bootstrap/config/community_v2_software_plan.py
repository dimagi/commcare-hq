from decimal import Decimal

from corehq.apps.accounting.models import FeatureType, SoftwarePlanEdition

BOOTSTRAP_CONFIG = {
    (SoftwarePlanEdition.COMMUNITY, False, False): {
        'role': 'community_plan_v2',
        'product_rate_monthly_fee': Decimal('0.00'),
        'feature_rates': {
            FeatureType.USER: dict(monthly_limit=5, per_excess_fee=Decimal('2.00')),
            FeatureType.SMS: dict(monthly_limit=0),
        }
    },
}
