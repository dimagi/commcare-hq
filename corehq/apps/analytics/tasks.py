from celery.task import task
import json
import requests
import urllib
import KISSmetrics

from settings import ANALYTICS_IDS


def _track_on_hubspot(webuser, properties):
    """
    Update or create a new "contact" on hubspot. Record that the user has
    created an account on HQ.

    properties is a dictionary mapping property names to values.
    Note that property names must exist on hubspot prior to use.
    """
    # Note: Hubspot recommends OAuth instead of api key
    # TODO: Use batch requests / be mindful of rate limit

    api_key = ANALYTICS_IDS.get('HUBSPOT_API_KEY', None)
    if api_key:
        req = requests.post(
            u"https://api.hubapi.com/contacts/v1/contact/createOrUpdate/email/{}".format(
                urllib.quote(webuser.username)
            ),
            params={'hapikey': api_key},
            data=json.dumps(
                {'properties': [
                    {'property': k, 'value': v} for k, v in properties.items()
                ]}
            ),
        )
        req.raise_for_status()


def _get_user_hubspot_id(webuser):
    api_key = ANALYTICS_IDS.get('HUBSPOT_API_KEY', None)
    if api_key:
        req = requests.get(
            u"https://api.hubapi.com/contacts/v1/contact/email/{}/profile".format(
                urllib.quote(webuser.username)
            ),
            params={'hapikey': api_key},
        )
        if req.status_code == 404:
            return None
        req.raise_for_status()
        return req.json().get("vid", None)
    return None


@task(queue='background_queue', acks_late=True, ignore_result=True)
def track_created_hq_account_on_hubspot(webuser):
    _track_on_hubspot(webuser, {
        'created_account_in_hq': True,
        'commcare_user': True,
    })


@task(queue='background_queue', acks_late=True, ignore_result=True)
def track_built_app_on_hubspot(webuser):
    vid = _get_user_hubspot_id(webuser)
    if vid:
        # Only track the property if the contact already exists.
        _track_on_hubspot(webuser, {'built_app': True})


@task(queue='background_queue', acks_late=True, ignore_result=True)
def track_workflow(email, event_or_properties, properties=None):
    """
    Record an event in KISSmetrics.
    :param email: The email address by which to identify the user.
    :param event_or_properties: The name of the event, or properties to set on the user.
    :param properties: A dictionary or properties to set on the user.
    :return:

    Examples:

        track_workflow("foo@bar.com", "Deployed App", {"is_dimagi": True})
        track_workflow("foo@bar.com", "Deployed App")
        track_workflow("foo@bar.com", {"is_dimagi": True})

    """
    if isinstance(event_or_properties, basestring):
        event = event_or_properties
    else:
        if properties:
            raise ValueError("The third argument may only be used if the "
                             "second argument is an event name.")
        event = None
        properties = event_or_properties


    api_key = ANALYTICS_IDS.get("KISSMETRICS_KEY", None)
    if api_key:
        km = KISSmetrics.Client(key=api_key)
        if event:
            km.record(email, event, properties if properties else {})
        else:
            km.set(email, properties if properties else {})

        # TODO: Consider adding some error handling for bad/failed requests.
