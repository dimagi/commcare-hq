from decimal import Decimal

from corehq.apps.accounting.models import (
    FeatureType,
    SoftwarePlanEdition,
)

BOOTSTRAP_CONFIG = {
    (SoftwarePlanEdition.COMMUNITY, False): {
        'role': 'community_plan_v0',
        'product_rate': dict(),
        'feature_rates': {
            FeatureType.USER: dict(monthly_limit=10, per_excess_fee=Decimal('1.00')),
            FeatureType.SMS: dict(monthly_limit=0),
        }
    }
}

BOOTSTRAP_CONFIG_TESTING = {
    (SoftwarePlanEdition.COMMUNITY, False): {
        'role': 'community_plan_v0',
        'product_rate': dict(),
        'feature_rates': {
            FeatureType.USER: dict(monthly_limit=2, per_excess_fee=Decimal('1.00')),
            FeatureType.SMS: dict(monthly_limit=0),
        }
    }
}
