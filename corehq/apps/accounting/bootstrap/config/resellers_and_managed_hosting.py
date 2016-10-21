from decimal import Decimal

from corehq.apps.accounting.models import (
    FeatureType,
    SoftwarePlanEdition,
)

BOOTSTRAP_EDITION_TO_ROLE = {
    SoftwarePlanEdition.MANAGED_HOSTING: 'managed_hosting_plan_v0',
    SoftwarePlanEdition.RESELLER: 'reseller_plan_v0',
}

BOOTSTRAP_PRODUCT_RATES = {
    SoftwarePlanEdition.RESELLER: [
        dict(monthly_fee=Decimal('1000.00')),
    ],
    SoftwarePlanEdition.MANAGED_HOSTING: [
        dict(monthly_fee=Decimal('1000.00')),
    ],
}

BOOTSTRAP_FEATURE_RATES = {
    SoftwarePlanEdition.RESELLER: {
        FeatureType.USER: dict(monthly_limit=10, per_excess_fee=Decimal('1.00')),
        FeatureType.SMS: dict(monthly_limit=0),
    },
    SoftwarePlanEdition.MANAGED_HOSTING: {
        FeatureType.USER: dict(monthly_limit=0, per_excess_fee=Decimal('1.00')),
        FeatureType.SMS: dict(monthly_limit=0),
    },
}

BOOTSTRAP_FEATURE_RATES_FOR_TESTING = {
    SoftwarePlanEdition.RESELLER: {
        FeatureType.USER: dict(monthly_limit=2, per_excess_fee=Decimal('1.00')),
        FeatureType.SMS: dict(monthly_limit=0),
    },
    SoftwarePlanEdition.MANAGED_HOSTING: {
        FeatureType.USER: dict(monthly_limit=0, per_excess_fee=Decimal('1.00')),
        FeatureType.SMS: dict(monthly_limit=0),
    },
}
