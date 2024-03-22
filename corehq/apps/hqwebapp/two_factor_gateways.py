import random

from django.contrib import messages
from django.contrib.sites.models import Site
from django.urls import reverse
from django.utils import translation
from django.utils.translation import pgettext
from django.utils.translation import gettext as _

from requests.compat import getproxies
from six.moves.urllib.parse import urlencode
from tastypie.http import HttpTooManyRequests
from twilio.base.exceptions import TwilioRestException
from twilio.http.http_client import TwilioHttpClient
from twilio.rest import Client
from two_factor.plugins.phonenumber.models import PhoneDevice

import settings
from corehq.apps.users.models import CouchUser
from corehq.messaging.smsbackends.twilio.models import SQLTwilioBackend
from corehq.project_limits.rate_limiter import RateLimiter, get_dynamic_rate_definition, \
    RateDefinition
from corehq.project_limits.models import RateLimitedTwoFactorLog
from corehq.util.decorators import run_only_when, silence_and_report_error
from corehq.util.global_request import get_request
from corehq.util.metrics import metrics_counter, metrics_gauge
from corehq.util.metrics.const import MPM_MAX
from dimagi.utils.logging import notify_exception
from dimagi.utils.web import get_ip

VOICE_LANGUAGES = ('en', 'en-gb', 'es', 'fr', 'it', 'de', 'da-DK', 'de-DE',
                   'en-AU', 'en-CA', 'en-GB', 'en-IN', 'en-US', 'ca-ES',
                   'es-ES', 'es-MX', 'fi-FI', 'fr-CA', 'fr-FR', 'it-IT',
                   'ja-JP', 'ko-KR', 'nb-NO', 'nl-NL', 'pl-PL', 'pt-BR',
                   'pt-PT', 'ru-RU', 'sv-SE', 'zh-CN', 'zh-HK', 'zh-TW')


class Gateway(object):

    def __init__(self):
        try:
            # try to pull a specially-named backend
            # this lets us separate out the backend used for 2FA specifically from the high-throughput backend.
            # (This allows the high-throughput backend not to support IVR calls, which are used for 2FA only.)
            backend = SQLTwilioBackend.objects.get(hq_api_id='TWILIO', name='TWILIO_TWO_FACTOR',
                                                   domain=None, deleted=False)
        except SQLTwilioBackend.DoesNotExist:
            backend = SQLTwilioBackend.objects.filter(hq_api_id='TWILIO', deleted=False, is_global=True)[0]

        sid = backend.extra_fields['account_sid']
        token = backend.extra_fields['auth_token']
        self.from_number = random.choice(backend.load_balancing_numbers)
        self.client = self._get_client(sid, token)

    def _get_client(self, sid, token):
        proxy_client = TwilioHttpClient()
        proxy_client.session.proxies = getproxies()
        return Client(sid, token, http_client=proxy_client)

    def send_sms(self, device, token):
        if rate_limit_two_factor_setup(device):
            return HttpTooManyRequests()

        message = _('Your authentication token is %s') % token
        try:
            self.client.api.account.messages.create(
                to=device.number.as_e164,
                from_=self.from_number,
                body=message)
        except TwilioRestException as e:
            request = get_request()
            notify_exception(request, str(e))
            if request:
                messages.error(request, _('''
                    Error received from SMS partner. If you do not receive a token, please retry in a few minutes.
                '''))

    def make_call(self, device, token):
        if rate_limit_two_factor_setup(device):
            return HttpTooManyRequests()

        locale = translation.get_language()
        validate_voice_locale(locale)

        url = reverse('two_factor_twilio:call_app', kwargs={'token': token})
        url = '%s?%s' % (url, urlencode({'locale': locale}))
        uri = 'https://%s%s' % (Site.objects.get_current().domain, url)
        self.client.api.account.calls.create(to=device.number.as_e164, from_=self.from_number, url=uri,
                                             method='GET', timeout='15')


def validate_voice_locale(locale):
    with translation.override(locale):
        voice_locale = pgettext('twilio_locale', 'en')
        if voice_locale not in VOICE_LANGUAGES:
            raise NotImplementedError('The language "%s" is not '
                                      'supported by Twilio' % voice_locale)


@run_only_when(not settings.ENTERPRISE_MODE and not settings.UNIT_TESTING)
@silence_and_report_error("Exception raised in the two factor setup rate limiter",
                          'commcare.two_factor.setup_rate_limiter_errors')
def rate_limit_two_factor_setup(device):
    """
    This holds attempts per IP OR per User OR per Number below limits
    given by two_factor_rate_limiter_per_ip, two_factor_rate_limiter_per_user,
    and two_factor_rate_limiter_per_number, respectively
    And keeps total requests below limits given by global_two_factor_setup_rate_limiter.

    Requests without an IP are rejected (unusual).
    If a device has no username attached or if it is not a PhoneDevice,
    then those requests are also rejected.

    """
    _status_global_rate_limited = 'global_rate_limited'
    _status_ip_rate_limited = 'ip_rate_limited'
    _status_number_rate_limited = 'number_rate_limited'
    _status_user_rate_limited = 'user_rate_limited'
    _status_bad_request = 'bad_request'
    _status_accepted = 'accepted'

    def get_ip_address():
        request = get_request()
        if request:
            return get_ip(request)
        else:
            return None

    def _check_for_exceeded_rate_limits(ip, num, user):
        global_window = global_two_factor_setup_rate_limiter.get_window_of_first_exceeded_limit()
        ip_window = two_factor_rate_limiter_per_ip.get_window_of_first_exceeded_limit('ip:{}'.format(ip))
        number_window = \
            two_factor_rate_limiter_per_number.get_window_of_first_exceeded_limit('number:{}'.format(num))
        user_window = two_factor_rate_limiter_per_user.get_window_of_first_exceeded_limit('user:{}'.format(user))

        # ensure that no rate limit windows have been exceeded
        # order of priority (global, ip, number, user)
        if global_window is not None:
            return _status_global_rate_limited, global_window
        elif ip_window is not None:
            return _status_ip_rate_limited, ip_window
        elif number_window is not None:
            return _status_number_rate_limited, number_window
        elif user_window is not None:
            return _status_user_rate_limited, user_window
        else:
            return _status_accepted, None

    _report_current_global_two_factor_setup_rate_limiter()

    ip_address = get_ip_address()
    number = device.number
    username = device.user.username
    method = device.method if isinstance(device, PhoneDevice) else None
    domain = None

    if ip_address and username and number and method:
        user = CouchUser.get_by_username(username)
        if user:
            if len(user.domain_memberships) == 1:
                domain = user.domain_memberships[0].domain
            else:
                domain = 'multiple'

        status, window = _check_for_exceeded_rate_limits(ip_address, number, username)
        if status == _status_accepted:
            _report_usage(ip_address, number, username)
        else:
            # log any attempts that are rate limited
            RateLimitedTwoFactorLog.objects.create(ip_address=ip_address, phone_number=number,
                                                   username=username, method=method,
                                                   status=status or 'unknown', window=window or 'unknown')

    else:
        window = None
        status = _status_bad_request

    metrics_counter('commcare.two_factor.setup_requests', 1, tags={
        'status': status,
        'method': method,
        'window': window or 'none',
        'domain': domain or 'none',
    })
    return status != _status_accepted


two_factor_rate_limiter_per_ip = RateLimiter(
    feature_key='two_factor_attempts_per_ip',
    get_rate_limits=lambda scope: get_dynamic_rate_definition(
        'two_factor_attempts_per_ip',
        default=RateDefinition(
            per_week=20000,
            per_day=2000,
            per_hour=1200,
            per_minute=700,
            per_second=60,
        )
    ).get_rate_limits(scope),
)

two_factor_rate_limiter_per_user = RateLimiter(
    feature_key='two_factor_attempts_per_user',
    get_rate_limits=lambda scope: get_dynamic_rate_definition(
        'two_factor_attempts_per_user',
        default=RateDefinition(
            per_week=120,
            per_day=40,
            per_hour=8,
            per_minute=2,
            per_second=1,
        )
    ).get_rate_limits(scope),
)

two_factor_rate_limiter_per_number = RateLimiter(
    feature_key='two_factor_attempts_per_number',
    get_rate_limits=lambda scope: get_dynamic_rate_definition(
        'two_factor_attempts_per_number',
        default=RateDefinition(
            per_week=120,
            per_day=40,
            per_hour=8,
            per_minute=2,
            per_second=1,
        )
    ).get_rate_limits(scope),
)

global_two_factor_setup_rate_limiter = RateLimiter(
    feature_key='global_two_factor_setup_attempts',
    get_rate_limits=lambda scope: get_dynamic_rate_definition(
        'global_two_factor_setup_attempts',
        default=RateDefinition(
            per_day=100,
        )
    ).get_rate_limits(),
)


def _report_usage(ip_address, number, username):
    global_two_factor_setup_rate_limiter.report_usage()
    two_factor_rate_limiter_per_ip.report_usage('ip:{}'.format(ip_address))
    two_factor_rate_limiter_per_number.report_usage('number:{}'.format(number))
    two_factor_rate_limiter_per_user.report_usage('user:{}'.format(username))


def _report_current_global_two_factor_setup_rate_limiter():
    for scope, limits in global_two_factor_setup_rate_limiter.iter_rates():
        for rate_counter, current_rate, threshold in limits:
            metrics_gauge('commcare.two_factor.global_two_factor_setup_threshold', threshold, tags={
                'window': rate_counter.key,
                'scope': scope
            }, multiprocess_mode=MPM_MAX)
            metrics_gauge('commcare.two_factor.global_two_factor_setup_usage', current_rate, tags={
                'window': rate_counter.key,
                'scope': scope
            }, multiprocess_mode=MPM_MAX)
