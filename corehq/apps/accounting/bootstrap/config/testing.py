from decimal import Decimal

from corehq.apps.accounting.models import (
    UNLIMITED_FEATURE_USAGE,
    FeatureType,
    SoftwarePlanEdition,
)

BOOTSTRAP_CONFIG_TESTING = {
    (SoftwarePlanEdition.COMMUNITY, False, False): {
        'role': 'community_plan_v1',
        'product_rate_monthly_fee': Decimal('0.00'),
        'feature_rates': {
            FeatureType.USER: dict(monthly_limit=2, per_excess_fee=Decimal('1.00')),
            FeatureType.SMS: dict(monthly_limit=0),
        }
    },
    (SoftwarePlanEdition.STANDARD, False, False): {
        'role': 'standard_plan_v0',
        'product_rate_monthly_fee': Decimal('300.00'),
        'feature_rates': {
            FeatureType.USER: dict(monthly_limit=4, per_excess_fee=Decimal('1.00')),
            FeatureType.SMS: dict(monthly_limit=3),
            FeatureType.WEB_USER: dict(monthly_limit=10, per_excess_fee=Decimal('10.00')),
        }
    },
    (SoftwarePlanEdition.PRO, False, False): {
        'role': 'pro_plan_v1',
        'product_rate_monthly_fee': Decimal('600.00'),
        'feature_rates': {
            FeatureType.USER: dict(monthly_limit=6, per_excess_fee=Decimal('1.00')),
            FeatureType.SMS: dict(monthly_limit=5),
        }
    },
    (SoftwarePlanEdition.ADVANCED, False, False): {
        'role': 'advanced_plan_v0',
        'product_rate_monthly_fee': Decimal('1200.00'),
        'feature_rates': {
            FeatureType.USER: dict(monthly_limit=8, per_excess_fee=Decimal('1.00')),
            FeatureType.SMS: dict(monthly_limit=7),
        }
    },
    (SoftwarePlanEdition.ADVANCED, True, False): {
        'role': 'advanced_plan_v0',
        'product_rate_monthly_fee': Decimal('0.00'),
        'feature_rates': {
            FeatureType.USER: dict(monthly_limit=2, per_excess_fee=Decimal('1.00')),
            FeatureType.SMS: dict(monthly_limit=0),
        }
    },
    (SoftwarePlanEdition.ENTERPRISE, False, False): {
        'role': 'enterprise_plan_v0',
        'product_rate_monthly_fee': Decimal('0.00'),
        'feature_rates': {
            FeatureType.USER: dict(monthly_limit=UNLIMITED_FEATURE_USAGE, per_excess_fee=Decimal('0.00')),
            FeatureType.SMS: dict(monthly_limit=UNLIMITED_FEATURE_USAGE),
        }
    },
}
