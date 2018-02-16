from __future__ import absolute_import
from corehq.apps.zapier.models import ZapierSubscription


def get_subscription_by_url(domain, url):
    try:
        return ZapierSubscription.objects.get(domain=domain, url=url)
    except ZapierSubscription.DoesNotExist:
        return None
