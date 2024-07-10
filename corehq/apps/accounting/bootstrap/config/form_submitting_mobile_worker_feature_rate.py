from decimal import Decimal
from corehq.apps.accounting.models import FeatureType

BOOTSTRAP_CONFIG = {
    "feature_rates": {
        FeatureType.FORM_SUBMITTING_MOBILE_WORKER: dict(monthly_limit=2000, per_excess_fee=Decimal('3.00'))
    }
}
