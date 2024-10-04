from decimal import Decimal

from corehq.apps.accounting.models import (
    UNLIMITED_FEATURE_USAGE,
    FeatureType,
    SoftwarePlanEdition,
)

BOOTSTRAP_CONFIG_TESTING = {
    (SoftwarePlanEdition.COMMUNITY, False, False, False): {
        'role': 'community_plan_v1',
        'product_rate_monthly_fee': Decimal('0.00'),
        'feature_rates': {
            FeatureType.USER: dict(monthly_limit=2, per_excess_fee=Decimal('1.00')),
            FeatureType.SMS: dict(monthly_limit=0),
        }
    },
    (SoftwarePlanEdition.STANDARD, False, False, False): {
        'role': 'standard_plan_v0',
        'product_rate_monthly_fee': Decimal('300.00'),
        'feature_rates': {
            FeatureType.USER: dict(monthly_limit=4, per_excess_fee=Decimal('1.00')),
            FeatureType.SMS: dict(monthly_limit=3),
            FeatureType.WEB_USER: dict(monthly_limit=10, per_excess_fee=Decimal('10.00')),
        }
    },
    (SoftwarePlanEdition.PRO, False, False, False): {
        'role': 'pro_plan_v1',
        'product_rate_monthly_fee': Decimal('600.00'),
        'feature_rates': {
            FeatureType.USER: dict(monthly_limit=6, per_excess_fee=Decimal('1.00')),
            FeatureType.SMS: dict(monthly_limit=5),
        }
    },
    (SoftwarePlanEdition.ADVANCED, False, False, False): {
        'role': 'advanced_plan_v0',
        'product_rate_monthly_fee': Decimal('1200.00'),
        'feature_rates': {
            FeatureType.USER: dict(monthly_limit=8, per_excess_fee=Decimal('1.00')),
            FeatureType.SMS: dict(monthly_limit=7),
        }
    },
    (SoftwarePlanEdition.ADVANCED, True, False, False): {
        'role': 'advanced_plan_v0',
        'product_rate_monthly_fee': Decimal('0.00'),
        'feature_rates': {
            FeatureType.USER: dict(monthly_limit=2, per_excess_fee=Decimal('1.00')),
            FeatureType.SMS: dict(monthly_limit=0),
        }
    },
    (SoftwarePlanEdition.ENTERPRISE, False, False, False): {
        'role': 'enterprise_plan_v0',
        'product_rate_monthly_fee': Decimal('0.00'),
        'feature_rates': {
            FeatureType.USER: dict(monthly_limit=UNLIMITED_FEATURE_USAGE, per_excess_fee=Decimal('0.00')),
            FeatureType.SMS: dict(monthly_limit=UNLIMITED_FEATURE_USAGE),
        }
    },
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
