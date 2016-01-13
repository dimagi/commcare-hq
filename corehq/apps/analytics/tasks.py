import csv
import os
from celery.schedules import crontab
from celery.task import task, periodic_task
import sys
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
from corehq.util.soft_assert import soft_assert
from corehq.apps.accounting.models import SoftwarePlanEdition

logger = logging.getLogger('analytics')
logger.setLevel('DEBUG')

HUBSPOT_SIGNUP_FORM_ID = "e86f8bea-6f71-48fc-a43b-5620a212b2a4"
HUBSPOT_SIGNIN_FORM_ID = "a2aa2df0-e4ec-469e-9769-0940924510ef"
HUBSPOT_FORM_BUILDER_FORM_ID = "4f118cda-3c73-41d9-a5d1-e371b23b1fb5"
HUBSPOT_APP_TEMPLATE_FORM_ID = "91f9b1d2-934d-4e7a-997e-e21e93d36662"
HUBSPOT_CLICKED_DEPLOY_FORM_ID = "c363c637-d0b1-44f3-9d73-f34c85559f03"
HUBSPOT_COOKIE = 'hubspotutk'


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


def _batch_track_on_hubspot(users_json):
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
        _log_response(data, response)
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


def _send_form_to_hubspot(form_id, webuser, cookies, meta):
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
            'email': webuser.username,
            'firstname': webuser.first_name,
            'lastname': webuser.last_name,
            'hs_context': json.dumps({"hutk": hubspot_cookie, "ipAddress": _get_client_ip(meta)}),
        }

        response = requests.post(
            url,
            data=data
        )
        _log_response(data, response)
        response.raise_for_status()


@task(queue='background_queue', acks_late=True, ignore_result=True)
def update_hubspot_properties(webuser, properties):
    vid = _get_user_hubspot_id(webuser)
    if vid:
        _track_on_hubspot(webuser, properties)


@task(queue='background_queue', acks_late=True, ignore_result=True)
def track_user_sign_in_on_hubspot(webuser, cookies, meta, path):
    if path.startswith(reverse("register_user")):
        _track_on_hubspot(webuser, {
            'created_account_in_hq': True,
            'is_a_commcare_user': True,
        })
        _send_form_to_hubspot(HUBSPOT_SIGNUP_FORM_ID, webuser, cookies, meta)
    _send_form_to_hubspot(HUBSPOT_SIGNIN_FORM_ID, webuser, cookies, meta)


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


@task(queue="background_queue", acks_late=True, ignore_result=True)
def track_entered_form_builder_on_hubspot(webuser, cookies, meta):
    _send_form_to_hubspot(HUBSPOT_FORM_BUILDER_FORM_ID, webuser, cookies, meta)


@task(queue="background_queue", acks_late=True, ignore_result=True)
def track_app_from_template_on_hubspot(webuser, cookies, meta):
    _send_form_to_hubspot(HUBSPOT_APP_TEMPLATE_FORM_ID, webuser, cookies, meta)


@task(queue="background_queue", acks_late=True, ignore_result=True)
def track_clicked_deploy_on_hubspot(webuser, cookies, meta):
    _send_form_to_hubspot(HUBSPOT_CLICKED_DEPLOY_FORM_ID, webuser, cookies, meta)


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


@task(queue='background_queue', acks_late=True, ignore_result=True)
def _track_workflow_task(email, event, properties=None, timestamp=0):
    api_key = settings.ANALYTICS_IDS.get("KISSMETRICS_KEY", None)
    if api_key:
        km = KISSmetrics.Client(key=api_key)
        km.record(email, event, properties if properties else {}, timestamp)
        # TODO: Consider adding some error handling for bad/failed requests.


@task(queue='background_queue', ignore_result=True)
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
        km.set(email, properties)
        # TODO: Consider adding some error handling for bad/failed requests.


@periodic_task(run_every=crontab(minute="0", hour="0"), queue='background_queue')
def track_periodic_data():
    """
    Sync data that is neither event or page based with hubspot/Kissmetrics
    :return:
    """
    start_time = datetime.now()
    # Start by getting a list of web users mapped to their domains
    six_months_ago = date.today() - timedelta(days=180)
    users_to_domains = UserES().web_users().last_logged_in(gte=six_months_ago).fields(['domains', 'email'])\
                               .run().hits
    # users_to_domains is a list of dicts
    time_users_to_domains_query = datetime.now()
    domains_to_forms = FormES().terms_facet('domain', 'domain').size(0).run().facets.domain.counts_by_term()
    time_domains_to_forms_query = datetime.now()
    domains_to_mobile_users = UserES().mobile_users().terms_facet('domain', 'domain').size(0).run()\
                                      .facets.domain.counts_by_term()
    time_domains_to_mobile_users_query = datetime.now()

    # For each web user, iterate through their domains and select the max number of form submissions and
    # max number of mobile workers
    submit = []
    for user in users_to_domains:
        email = user['email']
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
                }
            ]
        }
        submit.append(user_json)

    end_time = datetime.now()
    submit_json = json.dumps(submit)

    processing_time = end_time - start_time
    _soft_assert = soft_assert('{}@{}'.format('tsheffels', 'dimagi.com'))
    #TODO: Update this soft assert to only trigger if the timing is longer than a threshold
    msg = 'Periodic Data Timing: start: {}, users_to_domains: {}, domains_to_forms: {}, ' \
          'domains_to_mobile_workers: {}, end: {}, size of string post to hubspot (bytes): {}'\
        .format(
            start_time,
            time_users_to_domains_query,
            time_domains_to_forms_query,
            time_domains_to_mobile_users_query,
            end_time,
            sys.getsizeof(submit_json)
        )
    _soft_assert(processing_time.seconds < 10, msg)

    submit_data_to_hub_and_kiss(submit_json)


def submit_data_to_hub_and_kiss(submit_json):
    hubspot_dispatch = (_batch_track_on_hubspot, "Error submitting periodic analytics data to Hubspot")
    kissmetrics_dispatch = (
        _track_periodic_data_on_kiss, "Error submitting periodic analytics data to Kissmetrics"
    )

    for (dispatcher, error_message) in [hubspot_dispatch, kissmetrics_dispatch]:
        try:
            dispatcher(submit_json)
        except Exception, e:
            logger.error(error_message)
            logger.exception(e)


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


def _log_response(data, response):
    try:
        response_text = json.dumps(response.json(), indent=2, sort_keys=True)
    except Exception:
        response_text = response.status_code

    message = 'Sent this data to HS: %s \nreceived: %s' % (
        json.dumps(data, indent=2, sort_keys=True),
        response_text
    )

    if response.status_code != 200:
        logger.error(message)
    else:
        logger.debug(message)
