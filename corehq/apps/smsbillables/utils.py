import logging
import requests
import json

import boto3
from botocore.exceptions import ClientError

from django.conf import settings
from django.utils.encoding import force_text

from django_countries.data import COUNTRIES
from phonenumbers import COUNTRY_CODE_TO_REGION_CODE
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from corehq.apps.sms.models import SQLMobileBackend
from corehq.apps.smsbillables.exceptions import RetryBillableTaskException
from corehq.util.quickcache import quickcache

logger = logging.getLogger("smsbillables")


def country_name_from_isd_code_or_empty(isd_code):
    cc = COUNTRY_CODE_TO_REGION_CODE.get(isd_code)
    return force_text(COUNTRIES.get(cc[0])) if cc else ''


def log_smsbillables_error(message):
    if not settings.UNIT_TESTING:
        logger.error("[SMS Billables] %s" % message)


def log_smsbillables_info(message):
    if not settings.UNIT_TESTING:
        logger.info("[SMS Billables] %s" % message)


def _get_twilio_client(backend_instance):
    from corehq.messaging.smsbackends.twilio.models import SQLTwilioBackend
    twilio_backend = SQLMobileBackend.load(
        backend_instance,
        api_id=SQLTwilioBackend.get_api_id(),
        is_couch_id=True,
        include_deleted=True,
    )
    config = twilio_backend.config
    return Client(config.account_sid, config.auth_token)


@quickcache(vary_on=['backend_instance', 'backend_message_id'], timeout=1 * 60)
def get_twilio_message(backend_instance, backend_message_id):
    try:
        return _get_twilio_client(backend_instance).messages.get(backend_message_id).fetch()
    except TwilioRestException as e:
        raise RetryBillableTaskException(str(e))


@quickcache(vary_on=['backend_instance', 'backend_message_id'], timeout=1 * 60)
def get_infobip_message(backend_instance, backend_message_id):
    from corehq.messaging.smsbackends.infobip.models import InfobipBackend
    try:
        infobip_backend = SQLMobileBackend.load(
            backend_instance,
            api_id=InfobipBackend.get_api_id(),
            is_couch_id=True,
            include_deleted=True,
        )
        config = infobip_backend.config
        api_channel = '/sms/1'
        api_suffix = '/reports'
        if config.scenario_key:
            api_channel = '/omni/1'

        headers = {
            'Authorization': f'App {config.auth_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        parameters = {
            'messageId': backend_message_id
        }
        messages = _get_infobip_message_details(api_channel, api_suffix, config, headers, parameters)
        if not messages:
            api_suffix = '/logs'
            messages = _get_infobip_message_details(api_channel, api_suffix, config, headers, parameters)
        return messages[0]
    except Exception as e:
        raise RetryBillableTaskException(str(e))


def _get_infobip_message_details(api_channel, api_suffix, config, headers, parameters):
    from corehq.messaging.smsbackends.infobip.models import INFOBIP_DOMAIN
    url = f'https://{config.personalized_subdomain}.{INFOBIP_DOMAIN}{api_channel}{api_suffix}'
    response = requests.get(url, params=parameters, headers=headers)
    response_content = json.loads(response.content)
    messages = response_content['results']
    return messages


@quickcache(vary_on=['backend_instance', 'backend_message_id'], timeout=1 * 60)
def get_pinpoint_message(backend_instance, backend_message_id):
    from corehq.messaging.smsbackends.amazon_pinpoint.models import PinpointBackend
    try:
        pinpoint_backend = SQLMobileBackend.load(
            backend_instance,
            api_id=PinpointBackend.get_api_id(),
            is_couch_id=True,
            include_deleted=True,
        )
        pinpoint_service = 'logs'
        config = pinpoint_backend.config
        client = _get_pinpoint_client(backend_instance, pinpoint_service)
        response = client.filter_log_events(
            logGroupName=f'sns/{config.region}/754026553166/DirectPublishToPhoneNumber',
            filterPattern='{$.notification.messageId = %s}' % backend_message_id
        )
        return response['events'][0]
    except Exception as e:
        raise RetryBillableTaskException(str(e))


def _get_pinpoint_client(backend_instance, service):
    config = backend_instance.config
    client = boto3.client(
        service, region_name=config.region,
        aws_access_key_id=config.access_key, aws_secret_access_key=config.secret_access_key
    )
    return client
