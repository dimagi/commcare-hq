from decimal import Decimal

from corehq.apps.accounting.models import (
    FeatureType,
    SoftwarePlanEdition,
    UNLIMITED_FEATURE_USAGE,
)

BOOTSTRAP_EDITION_TO_ROLE = {
    SoftwarePlanEdition.COMMUNITY: 'community_plan_v0',
    SoftwarePlanEdition.STANDARD: 'standard_plan_v0',
    SoftwarePlanEdition.PRO: 'pro_plan_v0',
    SoftwarePlanEdition.ADVANCED: 'advanced_plan_v0',
    SoftwarePlanEdition.ENTERPRISE: 'enterprise_plan_v0',
}

FEATURE_TYPES = [
    FeatureType.USER,
    FeatureType.SMS,
]

BOOTSTRAP_PRODUCT_RATES = {
    SoftwarePlanEdition.COMMUNITY: dict(),
    SoftwarePlanEdition.STANDARD: dict(monthly_fee=Decimal('100.00')),
    SoftwarePlanEdition.PRO: dict(monthly_fee=Decimal('500.00')),
    SoftwarePlanEdition.ADVANCED: dict(monthly_fee=Decimal('1000.00')),
    SoftwarePlanEdition.ENTERPRISE: dict(monthly_fee=Decimal('0.00')),
}

BOOTSTRAP_FEATURE_RATES = {
    SoftwarePlanEdition.COMMUNITY: {
        FeatureType.USER: dict(monthly_limit=50, per_excess_fee=Decimal('1.00')),
        FeatureType.SMS: dict(monthly_limit=0),
    },
    SoftwarePlanEdition.STANDARD: {
        FeatureType.USER: dict(monthly_limit=100, per_excess_fee=Decimal('1.00')),
        FeatureType.SMS: dict(monthly_limit=100),
    },
    SoftwarePlanEdition.PRO: {
        FeatureType.USER: dict(monthly_limit=500, per_excess_fee=Decimal('1.00')),
        FeatureType.SMS: dict(monthly_limit=500),
    },
    SoftwarePlanEdition.ADVANCED: {
        FeatureType.USER: dict(monthly_limit=1000, per_excess_fee=Decimal('1.00')),
        FeatureType.SMS: dict(monthly_limit=1000),
    },
    SoftwarePlanEdition.ENTERPRISE: {
        FeatureType.USER: dict(monthly_limit=UNLIMITED_FEATURE_USAGE, per_excess_fee=Decimal('0.00')),
        FeatureType.SMS: dict(monthly_limit=UNLIMITED_FEATURE_USAGE),
    },
}

BOOTSTRAP_FEATURE_RATES_FOR_TESTING = {
    SoftwarePlanEdition.COMMUNITY: {
        FeatureType.USER: dict(monthly_limit=2, per_excess_fee=Decimal('1.00')),
        FeatureType.SMS: dict(monthly_limit=0),
    },
    SoftwarePlanEdition.STANDARD: {
        FeatureType.USER: dict(monthly_limit=4, per_excess_fee=Decimal('1.00')),
        FeatureType.SMS: dict(monthly_limit=3),
    },
    SoftwarePlanEdition.PRO: {
        FeatureType.USER: dict(monthly_limit=6, per_excess_fee=Decimal('1.00')),
        FeatureType.SMS: dict(monthly_limit=5),
    },
    SoftwarePlanEdition.ADVANCED: {
        FeatureType.USER: dict(monthly_limit=8, per_excess_fee=Decimal('1.00')),
        FeatureType.SMS: dict(monthly_limit=7),
    },
    SoftwarePlanEdition.ENTERPRISE: {
        FeatureType.USER: dict(monthly_limit=UNLIMITED_FEATURE_USAGE, per_excess_fee=Decimal('0.00')),
        FeatureType.SMS: dict(monthly_limit=UNLIMITED_FEATURE_USAGE),
    },
}
