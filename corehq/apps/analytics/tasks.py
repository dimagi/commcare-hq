from celery.task import task
import json
import requests
import urllib

from settings import ANALYTICS_IDS


def _track_on_hubspot(email, properties):
    """
    Update or create a new "contact" on hubspot. Record that the user has
    created an account on HQ.

    properties is a dictionary mapping property names to values.
    Note that property names must exist on hubspot prior to use.
    """
    # TODO: Use OAuth
    # TODO: Use batch requests / don't violate rate limit
    req = requests.post(
        "https://api.hubapi.com/contacts/v1/contact/createOrUpdate/email/{}".format(urllib.quote(email)),
        params={'hapikey': ANALYTICS_IDS.get('HUBSPOT_API_KEY', None)},
        data=json.dumps(
            {'properties': [
                {'property': k, 'value': v} for k, v in properties.items()
            ]}
        ),
    )
    req.raise_for_status()


@task(queue='background_queue')
def track_created_hq_account_on_hubspot(email):
    _track_on_hubspot(email, {'created_account_in_hq': True})


@task(queue='background_queue')
def track_built_app_on_hubspot(email):
    _track_on_hubspot(email, {'built_app': True})
