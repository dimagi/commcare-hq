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


def _get_client_ip(meta):
    x_forwarded_for = meta.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = meta.get('REMOTE_ADDR')
    return ip


def _link_account_with_cookie(webuser, cookies, meta):
    """
    This sends hubspot the user's first and last names and tracks everything they did
    up until the point they signed up.
    """
    HUBSPOT_SIGNUP_FORM_ID = "e86f8bea-6f71-48fc-a43b-5620a212b2a4"
    hubspot_id = ANALYTICS_IDS.get('HUBSPOT_ID')
    hubspot_cookie = cookies.get('hubspotutk')
    if hubspot_id:
        url = u"https://forms.hubspot.com/uploads/form/v2/{hubspot_id}/{form_id}".format(
            hubspot_id=hubspot_id,
            form_id=HUBSPOT_SIGNUP_FORM_ID
        )
        data = {
            'email': webuser.username,
            'firstname': webuser.first_name,
            'lastname': webuser.last_name,
            'hs_context': json.dumps({"hutk": hubspot_cookie, "ipAddress": _get_client_ip(meta)})
        }
        req = requests.post(
            url,
            data=data
        )
        req.raise_for_status()


@task(queue='background_queue', acks_late=True, ignore_result=True)
def track_created_hq_account_on_hubspot(webuser, cookies, meta):
    _track_on_hubspot(webuser, {
        'created_account_in_hq': True,
        'is_a_commcare_user': True,
    })
    _link_account_with_cookie(webuser, cookies, meta)


@task(queue='background_queue', acks_late=True, ignore_result=True)
def track_built_app_on_hubspot(webuser):
    vid = _get_user_hubspot_id(webuser)
    if vid:
        # Only track the property if the contact already exists.
        _track_on_hubspot(webuser, {'built_app': True})


@task(queue='background_queue', acks_late=True, ignore_result=True)
def track_confirmed_account_on_hubspot(webuser):
    vid = _get_user_hubspot_id(webuser)
    if vid:
        # Only track the property if the contact already exists.
        try:
            domain = webuser.domain_memberships[0].domain
        except (IndexError, AttributeError):
            domain = ''

        _track_on_hubspot(webuser, {
            'confirmed_account': True,
            'domain': domain
        })


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
