import logging
import requests
import json

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
    from corehq.messaging.smsbackends.infobip.models import INFOBIP_DOMAIN
    from corehq.messaging.smsbackends.infobip.models import InfobipBackend
    try:
        infobip_backend = SQLMobileBackend.load(
            backend_instance,
            api_id=InfobipBackend.get_api_id(),
            is_couch_id=True,
            include_deleted=True,
        )
        config = infobip_backend.config
        api_suffix = '/sms/1/reports'
        if config.scenario_key:
            api_suffix = '/omni/1/reports'

        headers = {
            'Authorization': f'App {config.auth_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        parameters = {
           'messageId': backend_message_id
        }
        url = f'https://{config.personalized_subdomain}.{INFOBIP_DOMAIN}{api_suffix}'
        response = requests.get(url, params=parameters, headers=headers)
        return json.loads(response.content)
    except Exception as e:
        raise RetryBillableTaskException(str(e))
