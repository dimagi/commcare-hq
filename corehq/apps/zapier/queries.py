from corehq.apps.zapier.consts import EventTypes
from corehq.apps.zapier.models import Subscription


def get_new_form_subscriptions(domain, xmlns):
    return Subscription.objects.filter(domain=domain, form_xmlns=xmlns, event_name=EventTypes.NEW_FORM)


def get_subscription_by_url(domain, url):
    try:
        return Subscription.objects.get(domain=domain, url=url)
    except Subscription.DoesNotExist:
        return None
