import csv
import os
from celery.schedules import crontab
from celery.task import periodic_task
import tinys3
from corehq.apps.domain.utils import get_domains_created_by_user
from corehq.apps.es.forms import FormES
from corehq.apps.es.users import UserES
from corehq.util.dates import unix_time
from datetime import datetime, date, timedelta
import time
import json
import requests
import urllib
import KISSmetrics
import logging

from django.conf import settings
from django.core.urlresolvers import reverse
from corehq.toggles import deterministic_random
from corehq.util.decorators import analytics_task

from dimagi.utils.logging import notify_exception


logger = logging.getLogger('analytics')
logger.setLevel('DEBUG')

HUBSPOT_SIGNUP_FORM_ID = "e86f8bea-6f71-48fc-a43b-5620a212b2a4"
HUBSPOT_SIGNIN_FORM_ID = "a2aa2df0-e4ec-469e-9769-0940924510ef"
HUBSPOT_FORM_BUILDER_FORM_ID = "4f118cda-3c73-41d9-a5d1-e371b23b1fb5"
HUBSPOT_APP_TEMPLATE_FORM_ID = "91f9b1d2-934d-4e7a-997e-e21e93d36662"
HUBSPOT_CLICKED_DEPLOY_FORM_ID = "c363c637-d0b1-44f3-9d73-f34c85559f03"
HUBSPOT_CREATED_NEW_PROJECT_SPACE_FORM_ID = "619daf02-e043-4617-8947-a23e4589935a"
HUBSPOT_INVITATION_SENT_FORM = "5aa8f696-4aab-4533-b026-bd64c7e06942"
HUBSPOT_NEW_USER_INVITE_FORM = "3e275361-72be-4e1d-9c68-893c259ed8ff"
HUBSPOT_EXISTING_USER_INVITE_FORM = "7533717e-3095-4072-85ff-96b139bcb147"
HUBSPOT_CLICKED_SIGNUP_FORM = "06b39b74-62b3-4387-b323-fe256dc92720"
HUBSPOT_CLICKED_PREVIEW_FORM_ID = "43124a42-972b-479e-a01a-6b92a484f7bc"
HUBSPOT_COOKIE = 'hubspotutk'


def _raise_for_urllib3_response(response):
    '''
    this mimics the behavior of requests.response.raise_for_status so we can
    treat kissmetrics requests and hubspot requests interchangeably in our retry code
    '''
    if 400 <= response.status < 600:
        raise requests.exceptions.HTTPError(response=response)


def _track_on_hubspot(webuser, properties):
    """
    Update or create a new "contact" on hubspot. Record that the user has
    created an account on HQ.

    properties is a dictionary mapping property names to values.
    Note that property names must exist on hubspot prior to use.
    """
    # Note: Hubspot recommends OAuth instead of api key

    _hubspot_post(
        url=u"https://api.hubapi.com/contacts/v1/contact/createOrUpdate/email/{}".format(
            urllib.quote(webuser.get_email())
        ),
        data=json.dumps(
            {'properties': [
                {'property': k, 'value': v} for k, v in properties.items()
            ]}
        ),
    )


def batch_track_on_hubspot(users_json):
    """
    Update or create contacts on hubspot in a batch request to prevent exceeding api rate limit

    :param users_json: Json that matches the hubspot api format
    [
        {
            "email": "testingapis@hubspot.com", #This can also be vid
            "properties": [
                {
                    "property": "firstname",
                    "value": "Codey"
                },
            ]
        },
    ]
    :return:
    """
    _hubspot_post(url=u'https://api.hubapi.com/contacts/v1/contact/batch/', data=users_json)


def _hubspot_post(url, data):
    """
    Lightweight wrapper to add hubspot api key and post data if the HUBSPOT_API_KEY is defined
    :param url: url to post to
    :param data: json data payload
    :return:
    """
    api_key = settings.ANALYTICS_IDS.get('HUBSPOT_API_KEY', None)
    if api_key:
        headers = {
            'content-type': 'application/json'
        }
        response = requests.post(
            url,
            params={'hapikey': api_key},
            data=data,
            headers=headers
        )
        _log_response('HS', data, response)
        response.raise_for_status()


def _get_user_hubspot_id(webuser):
    api_key = settings.ANALYTICS_IDS.get('HUBSPOT_API_KEY', None)
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


def _send_form_to_hubspot(form_id, webuser, cookies, meta, extra_fields=None, email=False):
    """
    This sends hubspot the user's first and last names and tracks everything they did
    up until the point they signed up.
    """
    hubspot_id = settings.ANALYTICS_IDS.get('HUBSPOT_API_ID')
    hubspot_cookie = cookies.get(HUBSPOT_COOKIE)
    if hubspot_id and hubspot_cookie:
        url = u"https://forms.hubspot.com/uploads/form/v2/{hubspot_id}/{form_id}".format(
            hubspot_id=hubspot_id,
            form_id=form_id
        )
        data = {
            'email': email if email else webuser.username,
            'hs_context': json.dumps({"hutk": hubspot_cookie, "ipAddress": _get_client_ip(meta)}),
        }
        if webuser:
            data.update({'firstname': webuser.first_name,
                         'lastname': webuser.last_name,
                         })
        if extra_fields:
            data.update(extra_fields)

        response = requests.post(
            url,
            data=data
        )
        _log_response('HS', data, response)
        response.raise_for_status()


@analytics_task()
def update_hubspot_properties(webuser, properties):
    vid = _get_user_hubspot_id(webuser)
    if vid:
        _track_on_hubspot(webuser, properties)


@analytics_task()
def track_user_sign_in_on_hubspot(webuser, cookies, meta, path):
    if path.startswith(reverse("register_user")):
        tracking_dict = {
            'created_account_in_hq': True,
            'is_a_commcare_user': True,
            'lifecyclestage': 'lead'
        }
        tracking_dict.update(get_ab_test_properties(webuser))
        _track_on_hubspot(webuser, tracking_dict)
        _send_form_to_hubspot(HUBSPOT_SIGNUP_FORM_ID, webuser, cookies, meta)
    _send_form_to_hubspot(HUBSPOT_SIGNIN_FORM_ID, webuser, cookies, meta)


@analytics_task()
def track_built_app_on_hubspot(webuser):
    vid = _get_user_hubspot_id(webuser)
    if vid:
        # Only track the property if the contact already exists.
        _track_on_hubspot(webuser, {'built_app': True})


@analytics_task()
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


@analytics_task()
def track_entered_form_builder_on_hubspot(webuser, cookies, meta):
    _send_form_to_hubspot(HUBSPOT_FORM_BUILDER_FORM_ID, webuser, cookies, meta)


@analytics_task()
def track_app_from_template_on_hubspot(webuser, cookies, meta):
    _send_form_to_hubspot(HUBSPOT_APP_TEMPLATE_FORM_ID, webuser, cookies, meta)


@analytics_task()
def track_clicked_deploy_on_hubspot(webuser, cookies, meta):
    ab = {
        'a_b_variable_deploy': 'A' if deterministic_random(webuser.username + 'a_b_variable_deploy') > 0.5 else 'B',
    }
    _send_form_to_hubspot(HUBSPOT_CLICKED_DEPLOY_FORM_ID, webuser, cookies, meta, extra_fields=ab)


@analytics_task()
def track_created_new_project_space_on_hubspot(webuser, cookies, meta):
    _send_form_to_hubspot(HUBSPOT_CREATED_NEW_PROJECT_SPACE_FORM_ID, webuser, cookies, meta)


@analytics_task()
def track_sent_invite_on_hubspot(webuser, cookies, meta):
    _send_form_to_hubspot(HUBSPOT_INVITATION_SENT_FORM, webuser, cookies, meta)


@analytics_task()
def track_existing_user_accepted_invite_on_hubspot(webuser, cookies, meta):
    _send_form_to_hubspot(HUBSPOT_INVITATION_SENT_FORM, webuser, cookies, meta)


@analytics_task()
def track_new_user_accepted_invite_on_hubspot(webuser, cookies, meta):
    _send_form_to_hubspot(HUBSPOT_NEW_USER_INVITE_FORM, webuser, cookies, meta)


@analytics_task()
def track_clicked_preview_on_hubspot(webuser, cookies, meta):
    _send_form_to_hubspot(HUBSPOT_CLICKED_PREVIEW_FORM_ID, webuser, cookies, meta)


@analytics_task()
def track_clicked_signup_on_hubspot(email, cookies, meta):
    data = {'lifecyclestage': 'subscriber'}
    number = deterministic_random(email + 'a_b_test_variable_newsletter')
    if number < 0.33:
        data['a_b_test_variable_newsletter'] = 'A'
    elif number < 0.67:
        data['a_b_test_variable_newsletter'] = 'B'
    else:
        data['a_b_test_variable_newsletter'] = 'C'
    if email:
        _send_form_to_hubspot(HUBSPOT_CLICKED_SIGNUP_FORM, None, cookies, meta, extra_fields=data, email=email)


def track_workflow(email, event, properties=None):
    """
    Record an event in KISSmetrics.
    :param email: The email address by which to identify the user.
    :param event: The name of the event.
    :param properties: A dictionary or properties to set on the user.
    :return:
    """
    timestamp = unix_time(datetime.utcnow())   # Dimagi KISSmetrics account uses UTC
    _track_workflow_task.delay(email, event, properties, timestamp)


@analytics_task()
def _track_workflow_task(email, event, properties=None, timestamp=0):
    api_key = settings.ANALYTICS_IDS.get("KISSMETRICS_KEY", None)
    if api_key:
        km = KISSmetrics.Client(key=api_key)
        res = km.record(email, event, properties if properties else {}, timestamp)
        _log_response("KM", {'email': email, 'event': event, 'properties': properties, 'timestamp': timestamp}, res)
        # TODO: Consider adding some better error handling for bad/failed requests.
        _raise_for_urllib3_response(res)


@analytics_task()
def identify(email, properties):
    """
    Set the given properties on a KISSmetrics user.
    :param email: The email address by which to identify the user.
    :param properties: A dictionary or properties to set on the user.
    :return:
    """
    api_key = settings.ANALYTICS_IDS.get("KISSMETRICS_KEY", None)
    if api_key:
        km = KISSmetrics.Client(key=api_key)
        res = km.set(email, properties)
        _log_response("KM", {'email': email, 'properties': properties}, res)
        # TODO: Consider adding some better error handling for bad/failed requests.
        _raise_for_urllib3_response(res)


@periodic_task(run_every=crontab(minute="0", hour="0"), queue='background_queue')
def track_periodic_data():
    """
    Sync data that is neither event or page based with hubspot/Kissmetrics
    :return:
    """
    # Start by getting a list of web users mapped to their domains
    six_months_ago = date.today() - timedelta(days=180)
    users_to_domains = UserES().web_users().last_logged_in(gte=six_months_ago).fields(['domains', 'email'])\
                               .run().hits
    # users_to_domains is a list of dicts
    domains_to_forms = FormES().terms_aggregation('domain', 'domain').size(0).run()\
        .aggregations.domain.counts_by_bucket()
    domains_to_mobile_users = UserES().mobile_users().terms_aggregation('domain', 'domain').size(0).run()\
                                      .aggregations.domain.counts_by_bucket()

    # For each web user, iterate through their domains and select the max number of form submissions and
    # max number of mobile workers
    submit = []
    for user in users_to_domains:
        email = user.get('email')
        if not email:
            continue
        max_forms = 0
        max_workers = 0

        for domain in user['domains']:
            if domain in domains_to_forms and domains_to_forms[domain] > max_forms:
                max_forms = domains_to_forms[domain]
            if domain in domains_to_mobile_users and domains_to_mobile_users[domain] > max_workers:
                max_workers = domains_to_mobile_users[domain]

        project_spaces_created = ", ".join(get_domains_created_by_user(email))

        user_json = {
            'email': email,
            'properties': [
                {
                    'property': 'max_form_submissions_in_a_domain',
                    'value': max_forms
                },
                {
                    'property': 'max_mobile_workers_in_a_domain',
                    'value': max_workers
                },
                {
                    'property': 'project_spaces_created_by_user',
                    'value': project_spaces_created,
                },
                {
                    'property': 'over_300_form_submissions',
                    'value': max_forms > 300
                }
            ]
        }
        submit.append(user_json)

    submit_json = json.dumps(submit)

    submit_data_to_hub_and_kiss(submit_json)


def submit_data_to_hub_and_kiss(submit_json):
    hubspot_dispatch = (batch_track_on_hubspot, "Error submitting periodic analytics data to Hubspot")
    kissmetrics_dispatch = (
        _track_periodic_data_on_kiss, "Error submitting periodic analytics data to Kissmetrics"
    )

    for (dispatcher, error_message) in [hubspot_dispatch, kissmetrics_dispatch]:
        try:
            dispatcher(submit_json)
        except Exception, e:
            notify_exception(None, u"{msg}: {exc}".format(msg=error_message, exc=e))


def _track_periodic_data_on_kiss(submit_json):
    """
    Transform periodic data into a format that is kissmetric submission friendly, then call identify
    csv format: Identity (email), timestamp (epoch), Prop:<Property name>, etc...
    :param submit_json: Example Json below, this function assumes
    [
      {
        email: <>,
        properties: [
          {
            property: <>,
            value: <>
          }, (can have more than one)
        ]
      }
    ]
    :return: none
    """
    periodic_data_list = json.loads(submit_json)

    headers = [
        'Identity',
        'Timestamp',
    ] + ['Prop:{}'.format(prop['property']) for prop in periodic_data_list[0]['properties']]

    filename = 'periodic_data.{}.csv'.format(date.today().strftime('%Y%m%d'))
    with open(filename, 'wb') as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow(headers)

        for webuser in periodic_data_list:
            row = [
                webuser['email'],
                int(time.time())
            ] + [prop['value'] for prop in webuser['properties']]
            csvwriter.writerow(row)

    if settings.S3_ACCESS_KEY and settings.S3_SECRET_KEY:
        s3_connection = tinys3.Connection(settings.S3_ACCESS_KEY, settings.S3_SECRET_KEY, tls=True)
        f = open(filename, 'rb')
        s3_connection.upload(filename, f, 'kiss-uploads')

    os.remove(filename)


def _log_response(target, data, response):
    status_code = response.status_code if isinstance(response, requests.models.Response) else response.status
    try:
        response_text = json.dumps(response.json(), indent=2, sort_keys=True)
    except Exception:
        response_text = status_code

    message = 'Sent this data to {target}: {data} \nreceived: {response}'.format(
        target=target,
        data=json.dumps(data, indent=2, sort_keys=True),
        response=response_text
    )

    if status_code != 200:
        logger.error(message)
    else:
        logger.debug(message)


def get_ab_test_properties(user):
    return {
        'a_b_test_variable_1':
            'A' if deterministic_random(user.username + 'a_b_test_variable_1') > 0.5 else 'B',
        'a_b_test_variable_first_submission':
            'A' if deterministic_random(user.username + 'a_b_test_variable_first_submission') > 0.5 else 'B',
    }
