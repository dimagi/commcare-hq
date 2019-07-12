from __future__ import absolute_import

from __future__ import unicode_literals
from __future__ import division
import csv342 as csv
import os

import math
from celery.schedules import crontab
from celery.task import periodic_task
import tinys3

from corehq.apps.accounting.models import (
    SubscriptionType, ProBonoStatus, SoftwarePlanVisibility,
    SoftwarePlanEdition, Subscription, DefaultProductPlan
)
from corehq.apps.domain.models import Domain
from corehq.apps.domain.utils import get_domains_created_by_user
from corehq.apps.es.forms import FormES
from corehq.apps.es.users import UserES
from corehq.apps.users.models import WebUser
from corehq.util.dates import unix_time
from corehq.apps.analytics.utils import get_instance_string, get_meta
from datetime import datetime, date, timedelta
import time
import json
import requests
import six.moves.urllib.request, six.moves.urllib.parse, six.moves.urllib.error
import KISSmetrics
import logging

from django.conf import settings
from email_validator import validate_email, EmailNotValidError
from corehq.toggles import deterministic_random
from corehq.util.decorators import analytics_task
from corehq.util.soft_assert import soft_assert
from corehq.util.datadog.utils import (
    count_by_response_code,
    update_datadog_metrics,
    DATADOG_DOMAINS_EXCEEDING_FORMS_GAUGE,
    DATADOG_WEB_USERS_GAUGE,
    DATADOG_HUBSPOT_SENT_FORM_METRIC,
    DATADOG_HUBSPOT_TRACK_DATA_POST_METRIC
)

from dimagi.utils.logging import notify_exception
from memoized import memoized

from corehq.apps.analytics.utils import analytics_enabled_for_email
from io import open
from six.moves import range

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
HUBSPOT_CREATED_EXPORT_FORM_ID = "f8a1ab5e-3fb5-4f68-948f-3355d09cf611"
HUBSPOT_DOWNLOADED_EXPORT_FORM_ID = "7db9de47-2dd1-44d0-a4ec-bb67d8052a9e"
HUBSPOT_SAVED_APP_FORM_ID = "8494a26a-8576-4241-97de-a28dc8bf927c"
HUBSPOT_SAVED_UCR_FORM_ID = "a0d64c4a-2e37-4f48-9700-b9831acdd1d9"
HUBSPOT_COOKIE = 'hubspotutk'
HUBSPOT_THRESHOLD = 300


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
    if webuser.analytics_enabled:
        # Note: Hubspot recommends OAuth instead of api key
        data = {'properties': [{'property': k, 'value': v} for k, v in properties.items()]}
        _hubspot_post(
            url="https://api.hubapi.com/contacts/v1/contact/createOrUpdate/email/{}".format(
                six.moves.urllib.parse.quote(webuser.get_email())
            ),
            data=json.dumps(data),
        )


def _track_on_hubspot_by_email(email, properties):
    # Note: Hubspot recommends OAuth instead of api key
    _hubspot_post(
        url="https://api.hubapi.com/contacts/v1/contact/createOrUpdate/email/{}".format(
            six.moves.urllib.parse.quote(email)
        ),
        data=json.dumps(
            {'properties': [
                {'property': k, 'value': v} for k, v in properties.items()
            ]}
        ),
    )


def set_analytics_opt_out(webuser, analytics_enabled):
    """
    Set 'opted_out' on the user whenever they change that, so we don't have
    opted out users throwing off metrics. This is handled separately because we
    (ironically) ignore the analytics_enabled flag.
    """
    _hubspot_post(
        url="https://api.hubapi.com/contacts/v1/contact/createOrUpdate/email/{}".format(
            six.moves.urllib.parse.quote(webuser.get_email())
        ),
        data=json.dumps(
            {'properties': [
                {'property': 'analytics_disabled', 'value': not analytics_enabled}
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
    _hubspot_post(url='https://api.hubapi.com/contacts/v1/contact/batch/', data=users_json)


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
        params = {'hapikey': api_key}
        response = _send_post_data(url, params, data, headers)
        _log_response('HS', data, response)
        response.raise_for_status()


@count_by_response_code(DATADOG_HUBSPOT_TRACK_DATA_POST_METRIC)
def _send_post_data(url, params, data, headers):
    return requests.post(url, params=params, data=data, headers=headers)


def _get_user_hubspot_id(webuser):
    api_key = settings.ANALYTICS_IDS.get('HUBSPOT_API_KEY', None)
    if api_key and webuser.analytics_enabled:
        req = requests.get(
            "https://api.hubapi.com/contacts/v1/contact/email/{}/profile".format(
                six.moves.urllib.parse.quote(webuser.username)
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


def _send_form_to_hubspot(form_id, webuser, hubspot_cookie, meta, extra_fields=None, email=False):
    """
    This sends hubspot the user's first and last names and tracks everything they did
    up until the point they signed up.
    """
    if ((webuser and not webuser.analytics_enabled)
            or (not webuser and not analytics_enabled_for_email(email))):
        # This user has analytics disabled
        return

    hubspot_id = settings.ANALYTICS_IDS.get('HUBSPOT_API_ID')
    if hubspot_id and hubspot_cookie:
        data = {
            'email': email if email else webuser.username,
            'hs_context': json.dumps({"hutk": hubspot_cookie, "ipAddress": _get_client_ip(meta)}),
        }
        if webuser:
            data.update({
                'firstname': webuser.first_name,
                'lastname': webuser.last_name,
            })
        if extra_fields:
            data.update(extra_fields)

        response = _send_hubspot_form_request(hubspot_id, form_id, data)
        _log_response('HS', data, response)
        response.raise_for_status()


@count_by_response_code(DATADOG_HUBSPOT_SENT_FORM_METRIC)
def _send_hubspot_form_request(hubspot_id, form_id, data):
    # Submits a urlencoded form, not JSON.  data should use "true"/"false" for bools
    # https://developers.hubspot.com/docs/methods/forms/submit_form
    url = "https://forms.hubspot.com/uploads/form/v2/{hubspot_id}/{form_id}".format(
        hubspot_id=hubspot_id,
        form_id=form_id
    )
    return requests.post(url, data=data)


@analytics_task(serializer='pickle', )
def update_hubspot_properties(webuser, properties):
    vid = _get_user_hubspot_id(webuser)
    if vid:
        _track_on_hubspot(webuser, properties)


def track_web_user_registration_hubspot(request, web_user, properties):
    if not settings.ANALYTICS_IDS.get('HUBSPOT_API_ID'):
        return

    tracking_info = {
        'created_account_in_hq': 'true',
        'is_a_commcare_user': 'true',
        'lifecyclestage': 'lead',
    }
    env = get_instance_string()
    tracking_info['{}date_created'.format(env)] = web_user.date_joined.isoformat()

    if (hasattr(web_user, 'phone_numbers') and len(web_user.phone_numbers) > 0):
        tracking_info.update({
            'phone': web_user.phone_numbers[0],
        })

    if web_user.atypical_user:
        tracking_info.update({
            'atypical_user': 'true'
        })

    tracking_info.update(get_ab_test_properties(web_user))
    tracking_info.update(properties)

    send_hubspot_form(
        HUBSPOT_SIGNUP_FORM_ID, request,
        user=web_user, extra_fields=tracking_info
    )


@analytics_task(serializer='pickle', )
def track_user_sign_in_on_hubspot(webuser, hubspot_cookie, meta, path):
    _send_form_to_hubspot(HUBSPOT_SIGNIN_FORM_ID, webuser, hubspot_cookie, meta)


@analytics_task(serializer='pickle', )
def track_built_app_on_hubspot(webuser):
    vid = _get_user_hubspot_id(webuser)
    if vid:
        # Only track the property if the contact already exists.
        _track_on_hubspot(webuser, {'built_app': True})


@analytics_task(serializer='pickle', )
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


def send_hubspot_form(form_id, request, user=None, extra_fields=None):
    """
    pulls out relevant info from request object before sending to celery since
    requests cannot be pickled
    """
    if user is None:
        user = getattr(request, 'couch_user', None)
    if request and user and user.is_web_user():
        meta = get_meta(request)
        send_hubspot_form_task.delay(
            form_id, user.user_id, request.COOKIES.get(HUBSPOT_COOKIE),
            meta, extra_fields=extra_fields
        )


@analytics_task()
def send_hubspot_form_task(form_id, web_user_id, hubspot_cookie, meta,
                              extra_fields=None):
    web_user = WebUser.get_by_user_id(web_user_id)
    _send_form_to_hubspot(form_id, web_user, hubspot_cookie, meta,
                          extra_fields=extra_fields)


@analytics_task(serializer='pickle', )
def track_clicked_deploy_on_hubspot(webuser, hubspot_cookie, meta):
    ab = {
        'a_b_variable_deploy': 'A' if deterministic_random(webuser.username + 'a_b_variable_deploy') > 0.5 else 'B',
    }
    _send_form_to_hubspot(HUBSPOT_CLICKED_DEPLOY_FORM_ID, webuser, hubspot_cookie, meta, extra_fields=ab)


@analytics_task(serializer='pickle', )
def track_job_candidate_on_hubspot(user_email):
    properties = {
        'job_candidate': True
    }
    _track_on_hubspot_by_email(user_email, properties=properties)


@analytics_task(serializer='pickle', )
def track_clicked_signup_on_hubspot(email, hubspot_cookie, meta):
    data = {'lifecyclestage': 'subscriber'}
    number = deterministic_random(email + 'a_b_test_variable_newsletter')
    if number < 0.33:
        data['a_b_test_variable_newsletter'] = 'A'
    elif number < 0.67:
        data['a_b_test_variable_newsletter'] = 'B'
    else:
        data['a_b_test_variable_newsletter'] = 'C'
    if email:
        _send_form_to_hubspot(
            HUBSPOT_CLICKED_SIGNUP_FORM, None, hubspot_cookie,
            meta, extra_fields=data, email=email
        )


def track_workflow(email, event, properties=None):
    """
    Record an event in KISSmetrics.
    :param email: The email address by which to identify the user.
    :param event: The name of the event.
    :param properties: A dictionary or properties to set on the user.
    :return:
    """
    try:
        if analytics_enabled_for_email(email):
            timestamp = unix_time(datetime.utcnow())   # Dimagi KISSmetrics account uses UTC
            _track_workflow_task.delay(email, event, properties, timestamp)
    except Exception:
        notify_exception(None, "Error tracking kissmetrics workflow")


@analytics_task(serializer='pickle', )
def _track_workflow_task(email, event, properties=None, timestamp=0):
    def _no_nonascii_unicode(value):
        if isinstance(value, six.text_type):
            return value.encode('utf-8')
        return value

    api_key = settings.ANALYTICS_IDS.get("KISSMETRICS_KEY", None)
    if api_key:
        km = KISSmetrics.Client(key=api_key)
        res = km.record(
            email,
            event,
            {_no_nonascii_unicode(k): _no_nonascii_unicode(v) for k, v in six.iteritems(properties)} if properties else {},
            timestamp
        )
        _log_response("KM", {'email': email, 'event': event, 'properties': properties, 'timestamp': timestamp}, res)
        # TODO: Consider adding some better error handling for bad/failed requests.
        _raise_for_urllib3_response(res)


@analytics_task(serializer='pickle', )
def identify(email, properties):
    """
    Set the given properties on a KISSmetrics user.
    :param email: The email address by which to identify the user.
    :param properties: A dictionary or properties to set on the user.
    :return:
    """
    api_key = settings.ANALYTICS_IDS.get("KISSMETRICS_KEY", None)
    if api_key and analytics_enabled_for_email(email):
        km = KISSmetrics.Client(key=api_key)
        res = km.set(email, properties)
        _log_response("KM", {'email': email, 'properties': properties}, res)
        # TODO: Consider adding some better error handling for bad/failed requests.
        _raise_for_urllib3_response(res)


@memoized
def _get_export_count(domain):
    from corehq.apps.export.dbaccessors import get_export_count_by_domain

    return get_export_count_by_domain(domain)


@memoized
def _get_report_count(domain):
    from corehq.reports import get_report_builder_count

    return get_report_builder_count(domain)


@periodic_task(run_every=crontab(minute="0", hour="4"), queue='background_queue')
def track_periodic_data():
    """
    Sync data that is neither event or page based with hubspot/Kissmetrics
    :return:
    """
    # Start by getting a list of web users mapped to their domains
    three_months_ago = date.today() - timedelta(days=90)

    user_query = (UserES()
                  .web_users()
                  .last_logged_in(gte=three_months_ago)
                  .sort('date_joined', desc=True)
                  .source(['domains', 'email', 'date_joined'])
                  .analytics_enabled())

    total_users = user_query.count()
    chunk_size = 100
    num_chunks = int(math.ceil(float(total_users) / float(chunk_size)))

    # Track no of users and domains with max_forms greater than HUBSPOT_THRESHOLD
    hubspot_number_of_users = 0
    hubspot_number_of_domains_with_forms_gt_threshold = 0

    for chunk in range(num_chunks):
        users_to_domains = (user_query
                            .size(chunk_size)
                            .start(chunk * chunk_size)
                            .run()
                            .hits)

        # users_to_domains is a list of dicts
        domains_to_forms = (FormES()
                            .terms_aggregation('domain', 'domain')
                            .size(0)
                            .run()
                            .aggregations.domain.counts_by_bucket())
        domains_to_mobile_users = (UserES()
                                   .mobile_users()
                                   .terms_aggregation('domain', 'domain')
                                   .size(0)
                                   .run()
                                   .aggregations
                                   .domain
                                   .counts_by_bucket())

        # Keep track of india and www data seperately
        env = get_instance_string()

        for num_forms in domains_to_forms.values():
            if num_forms > HUBSPOT_THRESHOLD:
                hubspot_number_of_domains_with_forms_gt_threshold += 1

        # For each web user, iterate through their domains and select the max number of form submissions and
        # max number of mobile workers
        submit = []
        for user in users_to_domains:
            email = user.get('email')
            if not _email_is_valid(email):
                continue

            hubspot_number_of_users += 1
            date_created = user.get('date_joined')
            max_forms = 0
            max_workers = 0
            max_export = 0
            max_report = 0

            for domain in user['domains']:
                if domain in domains_to_forms and domains_to_forms[domain] > max_forms:
                    max_forms = domains_to_forms[domain]
                if domain in domains_to_mobile_users and domains_to_mobile_users[domain] > max_workers:
                    max_workers = domains_to_mobile_users[domain]
                if _get_export_count(domain) > max_export:
                    max_export = _get_export_count(domain)
                if _get_report_count(domain) > max_report:
                    max_report = _get_report_count(domain)

            project_spaces_created = ", ".join(get_domains_created_by_user(email))

            user_json = {
                'email': email,
                'properties': [
                    {
                        'property': '{}max_form_submissions_in_a_domain'.format(env),
                        'value': max_forms
                    },
                    {
                        'property': '{}max_mobile_workers_in_a_domain'.format(env),
                        'value': max_workers
                    },
                    {
                        'property': '{}project_spaces_created_by_user'.format(env),
                        'value': project_spaces_created,
                    },
                    {
                        'property': '{}over_300_form_submissions'.format(env),
                        'value': max_forms > HUBSPOT_THRESHOLD
                    },
                    {
                        'property': '{}date_created'.format(env),
                        'value': date_created
                    },
                    {
                        'property': '{}max_exports_in_a_domain'.format(env),
                        'value': max_export
                    },
                    {
                        'property': '{}max_custom_reports_in_a_domain'.format(env),
                        'value': max_report
                    }
                ]
            }
            submit.append(user_json)

        submit_json = json.dumps(submit)
        submit_data_to_hub_and_kiss(submit_json)

    update_datadog_metrics({
        DATADOG_WEB_USERS_GAUGE: hubspot_number_of_users,
        DATADOG_DOMAINS_EXCEEDING_FORMS_GAUGE: hubspot_number_of_domains_with_forms_gt_threshold
    })


def _email_is_valid(email):
    if not email:
        return False

    try:
        validate_email(email)
    except EmailNotValidError as e:
        logger.warn(str(e))
        return False

    return True


def submit_data_to_hub_and_kiss(submit_json):
    hubspot_dispatch = (batch_track_on_hubspot, "Error submitting periodic analytics data to Hubspot")
    kissmetrics_dispatch = (
        _track_periodic_data_on_kiss, "Error submitting periodic analytics data to Kissmetrics"
    )

    for (dispatcher, error_message) in [hubspot_dispatch, kissmetrics_dispatch]:
        try:
            dispatcher(submit_json)
        except requests.exceptions.HTTPError as e:
            soft_assert(to=[settings.SUPPORT_EMAIL,
                            '{}@{}'.format('miemma', 'dimagi.com'),
                            '{}@{}'.format('aphilippot', 'dimagi.com'),
                            '{}@{}'.format('colaughlin', 'dimagi.com')],
                        send_to_ops=False)(False,
                                           'Error submitting periodic analytics data to Hubspot or Kissmetrics',
                                           {'response': e.response.content.decode('utf-8')})
        except Exception as e:
            notify_exception(None, "{msg}: {exc}".format(msg=error_message, exc=e))


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
    with open(filename, 'w') as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow(headers)

        for webuser in periodic_data_list:
            row = [
                webuser['email'],
                int(time.time())
            ] + [prop['value'] for prop in webuser['properties']]
            csvwriter.writerow(row)

    if settings.S3_ACCESS_KEY and settings.S3_SECRET_KEY and settings.ANALYTICS_IDS.get('KISSMETRICS_KEY', None):
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


@analytics_task()  # TODO - remove analytics_task decorator after changes are deployed to all environments.
def update_subscription_properties_by_domain(domain):
    domain_obj = Domain.get_by_name(domain)
    if domain_obj:
        affected_users = WebUser.view(
            'users/web_users_by_domain', reduce=False, key=domain, include_docs=True
        ).all()

        for web_user in affected_users:
            properties = get_subscription_properties_by_user(web_user)
            update_subscription_properties_by_user.delay(web_user.get_id, properties)


@analytics_task()
def update_subscription_properties_by_user(web_user_id, properties):
    web_user = WebUser.get_by_user_id(web_user_id)
    identify(web_user.username, properties)
    update_hubspot_properties(web_user, properties)


def get_subscription_properties_by_user(couch_user):

    def _is_paying_subscription(subscription, plan_version):
        NON_PAYING_SERVICE_TYPES = [
            SubscriptionType.TRIAL,
            SubscriptionType.EXTENDED_TRIAL,
            SubscriptionType.SANDBOX,
            SubscriptionType.INTERNAL,
        ]

        NON_PAYING_PRO_BONO_STATUSES = [
            ProBonoStatus.YES,
            ProBonoStatus.DISCOUNTED,
        ]
        return (plan_version.plan.visibility != SoftwarePlanVisibility.TRIAL and
                subscription.service_type not in NON_PAYING_SERVICE_TYPES and
                subscription.pro_bono_status not in NON_PAYING_PRO_BONO_STATUSES and
                plan_version.plan.edition != SoftwarePlanEdition.COMMUNITY)

    # Note: using "yes" and "no" instead of True and False because spec calls
    # for using these values. (True is just converted to "True" in KISSmetrics)
    all_subscriptions = []
    paying_subscribed_editions = []
    subscribed_editions = []
    for domain_name in couch_user.domains:
        subscription = Subscription.get_active_subscription_by_domain(domain_name)
        plan_version = (
            subscription.plan_version
            if subscription is not None
            else DefaultProductPlan.get_default_plan_version()
        )
        subscribed_editions.append(plan_version.plan.edition)
        if subscription is not None:
            all_subscriptions.append(subscription)
            if _is_paying_subscription(subscription, plan_version):
                paying_subscribed_editions.append(plan_version.plan.edition)

    def _is_one_of_editions(edition):
        return 'yes' if edition in subscribed_editions else 'no'

    def _is_a_pro_bono_status(status):
        return 'yes' if status in [s.pro_bono_status for s in all_subscriptions] else 'no'

    def _is_on_extended_trial():
        service_types = [s.service_type for s in all_subscriptions]
        return 'yes' if SubscriptionType.EXTENDED_TRIAL in service_types else 'no'

    def _max_edition():
        for edition in paying_subscribed_editions:
            assert edition in [e[0] for e in SoftwarePlanEdition.CHOICES]

        return max(paying_subscribed_editions) if paying_subscribed_editions else ''

    env = get_instance_string()

    return {
        '{}is_on_community_plan'.format(env): _is_one_of_editions(SoftwarePlanEdition.COMMUNITY),
        '{}is_on_standard_plan'.format(env): _is_one_of_editions(SoftwarePlanEdition.STANDARD),
        '{}is_on_pro_plan'.format(env): _is_one_of_editions(SoftwarePlanEdition.PRO),
        '{}is_on_pro_bono_plan'.format(env): _is_a_pro_bono_status(ProBonoStatus.YES),
        '{}is_on_discounted_plan'.format(env): _is_a_pro_bono_status(ProBonoStatus.DISCOUNTED),
        '{}is_on_extended_trial_plan'.format(env): _is_on_extended_trial(),
        '{}max_edition_of_paying_plan'.format(env): _max_edition()
    }
