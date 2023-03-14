from corehq.toggles import all_toggles

from corehq.apps.accounting.models import Subscription
from corehq.apps.es import UserES
from corehq.util.quickcache import quickcache


def find_static_toggle(slug):
    for toggle in all_toggles():
        if toggle.slug == slug:
            return toggle


@quickcache(['domain'], timeout=60 * 10)
def get_subscription_info(domain):
    subscription = Subscription.get_active_subscription_by_domain(domain)
    if subscription:
        return subscription.service_type, subscription.plan_version.plan.name
    return None, None


@quickcache(['domain'], timeout=60 * 10)
def has_dimagi_user(domain):
    search_fields = ["base_username", "username"]
    return UserES().web_users().domain(domain).search_string_query('@dimagi.com', search_fields).count()
