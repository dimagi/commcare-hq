from celery.task import task
import json
import requests
import urllib

from settings import ANALYTICS_IDS


def _track_on_hubspot(webuser, properties, update_only=False):
    """
    Update or create a new "contact" on hubspot. Record that the user has
    created an account on HQ.

    properties is a dictionary mapping property names to values.
    Note that property names must exist on hubspot prior to use.
    """
    # Note: Hubspot recommends OAuth instead of api key
    # TODO: Use batch requests / be mindful of rate limit
    api_key = ANALYTICS_IDS.get('HUBSPOT_API_KEY', None)
    url = "https://api.hubapi.com/contacts/v1/contact/createOrUpdate/email/{}"
    if update_only:
        url = "https://api.hubapi.com/contacts/v1/contact/email/{}/profile"

    if api_key and not webuser.is_dimagi:
        req = requests.post(
            url.format(urllib.quote(webuser.username)),
            params={'hapikey': api_key},
            data=json.dumps(
                {'properties': [
                    {'property': k, 'value': v} for k, v in properties.items()
                ]}
            ),
        )
        req.raise_for_status()


@task(queue='background_queue', acks_late=True)
def track_created_hq_account_on_hubspot(webuser):
    _track_on_hubspot(webuser, {
        'created_account_in_hq': True,
        'commcare_user': True,
    })


@task(queue='background_queue', acks_late=True)
def track_built_app_on_hubspot(webuser):
    _track_on_hubspot(webuser, {'built_app': True}, update_only=True)
