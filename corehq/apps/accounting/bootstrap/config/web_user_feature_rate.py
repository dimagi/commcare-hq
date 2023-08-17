from decimal import Decimal
from corehq.apps.accounting.models import FeatureType

BOOTSTRAP_CONFIG = {
    "feature_rates": {
        FeatureType.WEB_USER: dict(monthly_limit=10, per_excess_fee=Decimal('10.00'))
    }
}
