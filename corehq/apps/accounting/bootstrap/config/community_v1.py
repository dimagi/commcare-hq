from decimal import Decimal

from corehq.apps.accounting.models import (
    FeatureType,
    SoftwarePlanEdition,
    SoftwareProductType,
)

BOOTSTRAP_EDITION_TO_ROLE = {
    SoftwarePlanEdition.COMMUNITY: 'community_plan_v1',
}

FEATURE_TYPES = [
    FeatureType.USER,
    FeatureType.SMS,
]

PRODUCT_TYPES = [
    SoftwareProductType.COMMCARE,
    SoftwareProductType.COMMCONNECT,
    SoftwareProductType.COMMTRACK,
]

BOOTSTRAP_PRODUCT_RATES = {
    SoftwarePlanEdition.COMMUNITY: dict(),
}

BOOTSTRAP_FEATURE_RATES = {
    SoftwarePlanEdition.COMMUNITY: {
        FeatureType.USER: dict(monthly_limit=10, per_excess_fee=Decimal('1.00')),
        FeatureType.SMS: dict(monthly_limit=0),
    },
}

BOOTSTRAP_FEATURE_RATES_FOR_TESTING = {
    SoftwarePlanEdition.COMMUNITY: {
        FeatureType.USER: dict(monthly_limit=2, per_excess_fee=Decimal('1.00')),
        FeatureType.SMS: dict(monthly_limit=0),
    },
}
