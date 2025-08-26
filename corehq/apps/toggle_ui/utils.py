from corehq.toggles import all_toggles

from corehq.apps.accounting.models import Subscription
from corehq.apps.es import UserES


def find_static_toggle(slug):
    for toggle in all_toggles():
        if toggle.slug == slug:
            return toggle


def get_subscription_info(domain):
    subscription = Subscription.get_active_subscription_by_domain(domain)
    if subscription:
        return subscription.service_type, subscription.plan_version.plan.name
    return None, None


def get_dimagi_users(domain):
    res = (
        UserES()
        .web_users()
        .domain(domain)
        .term('username', 'dimagi.com')
        .size(10)
        .source('username')
        .run()
    )
    usernames = [r['username'] for r in res.hits]
    if res.total > 10:
        usernames.append('...')
    return ', '.join(usernames)
