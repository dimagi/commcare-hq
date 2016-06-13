import celery

from corehq.apps.zapier.queries import get_new_form_subscriptions
from corehq.apps.zapier.utils import convert_xform_to_json


@celery.task
def send_to_subscribers_task(domain, xform):
    for subscription in get_new_form_subscriptions(domain, xform.xmlns):
        response = subscription.send_to_subscriber(convert_xform_to_json(xform))
        if response.status_code == 410:
            # https://zapier.com/developer/documentation/v2/rest-hooks/
            # If Zapier responds with a 410 status code
            # you should immediately remove the subscription to the failing hook (unsubscribe).
            subscription.delete()
