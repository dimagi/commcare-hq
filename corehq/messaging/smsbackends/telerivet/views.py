import uuid
from corehq.apps.sms.models import SMS
from corehq.apps.sms.util import clean_phone_number
from corehq.apps.sms.views import BaseMessagingSectionView
from corehq.apps.style.decorators import use_bootstrap3, use_angular_js
from corehq.messaging.smsbackends.telerivet.tasks import process_incoming_message
from corehq.messaging.smsbackends.telerivet.forms import (TelerivetOutgoingSMSForm,
    TelerivetPhoneNumberForm, FinalizeGatewaySetupForm)
from corehq.messaging.smsbackends.telerivet.models import IncomingRequest, SQLTelerivetBackend
from corehq.util.view_utils import absolute_reverse
from dimagi.utils.couch.cache.cache_core import get_redis_client
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils.translation import ugettext_lazy
from djangular.views.mixins import JSONResponseMixin, allow_remote_invocation


# Tuple of (hq field name, telerivet field name) tuples
TELERIVET_INBOUND_FIELD_MAP = (
    ('event', 'event'),
    ('message_id', 'id'),
    ('message_type', 'message_type'),
    ('content', 'content'),
    ('from_number', 'from_number'),
    ('from_number_e164', 'from_number_e164'),
    ('to_number', 'to_number'),
    ('time_created', 'time_created'),
    ('time_sent', 'time_sent'),
    ('contact_id', 'contact_id'),
    ('phone_id', 'phone_id'),
    ('service_id', 'service_id'),
    ('project_id', 'project_id'),
    ('secret', 'secret'),
)


@require_POST
@csrf_exempt
def incoming_message(request):
    kwargs = {a: request.POST.get(b) for (a, b) in TELERIVET_INBOUND_FIELD_MAP}
    process_incoming_message.delay(**kwargs)
    return HttpResponse()


class TelerivetSetupView(JSONResponseMixin, BaseMessagingSectionView):
    template_name = 'telerivet/telerivet_setup.html'
    urlname = 'telerivet_setup'
    page_title = ugettext_lazy("Telerivet Setup")

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    def get_cache_key(self, request_token):
        return 'telerivet-setup-%s' % request_token

    def set_cached_webhook_secret(self, request_token, webhook_secret):
        client = get_redis_client()
        key = self.get_cache_key(request_token)
        client.set(key, webhook_secret)
        client.expire(key, 7 * 24 * 60 * 60)

    def get_cached_webhook_secret(self, request_token):
        client = get_redis_client()
        key = self.get_cache_key(request_token)
        return client.get(key)

    @property
    def page_context(self):
        # The webhook secret is a piece of data that is sent to hq on each
        # Telerivet inbound request. It's used to tie an inbound request to
        # a Telerivet backend.
        webhook_secret = uuid.uuid4().hex

        # The request token is only used for the purposes of using this UI to
        # setup a Telerivet backend. We need a way to post the webhook_secret
        # to create the backend, but we want hq to be the origin of the secret
        # generation. So instead, the request_token resolves to the webhook_secret
        # via a redis lookup which expires in 1 week.
        request_token = uuid.uuid4().hex

        self.set_cached_webhook_secret(request_token, webhook_secret)
        return {
            'outgoing_sms_form': TelerivetOutgoingSMSForm(),
            'test_sms_form': TelerivetPhoneNumberForm(),
            'finalize_gateway_form': FinalizeGatewaySetupForm(),
            'webhook_url': absolute_reverse('telerivet_in'),
            'webhook_secret': webhook_secret,
            'request_token': request_token,
        }

    @allow_remote_invocation
    def get_last_inbound_sms(self, data):
        request_token = data.get('request_token')
        if not request_token:
            return {'success': False}

        webhook_secret = self.get_cached_webhook_secret(request_token)
        if not webhook_secret:
            return {'success': False}

        result = IncomingRequest.get_last_sms_by_webhook_secret(webhook_secret)
        if result:
            return {
                'success': True,
                'found': True,
            }
        else:
            return {
                'success': True,
                'found': False,
            }

    @allow_remote_invocation
    def send_sample_sms(self, data):
        api_key = data.get('api_key')
        project_id = data.get('project_id')
        phone_id = data.get('phone_id')
        test_phone_number = data.get('test_phone_number')
        request_token = data.get('request_token')

        if not (
            api_key and
            project_id and
            phone_id and
            test_phone_number and
            request_token and
            self.get_cached_webhook_secret(request_token)
        ):
            return {
                'success': False,
            }

        tmp_backend = SQLTelerivetBackend()
        tmp_backend.set_extra_fields(
            api_key=api_key,
            project_id=project_id,
            phone_id=phone_id,
        )
        sms = SMS(
            phone_number=clean_phone_number(test_phone_number),
            text="This is a test SMS from CommCareHQ."
        )
        tmp_backend.send(sms)
        return {
            'success': True,
        }

    @use_bootstrap3
    @use_angular_js
    def dispatch(self, *args, **kwargs):
        return super(TelerivetSetupView, self).dispatch(*args, **kwargs)
