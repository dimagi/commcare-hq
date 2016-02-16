import uuid
from corehq.apps.sms.models import SMS, SQLMobileBackend, SQLMobileBackendMapping
from corehq.apps.sms.util import clean_phone_number
from corehq.apps.sms.views import BaseMessagingSectionView
from corehq.apps.style.decorators import use_bootstrap3, use_angular_js
from corehq.messaging.smsbackends.telerivet.tasks import process_incoming_message
from corehq.messaging.smsbackends.telerivet.forms import (TelerivetOutgoingSMSForm,
    TelerivetPhoneNumberForm, FinalizeGatewaySetupForm, TelerivetBackendForm)
from corehq.messaging.smsbackends.telerivet.models import IncomingRequest, SQLTelerivetBackend
from corehq.util.view_utils import absolute_reverse
from dimagi.utils.couch.cache.cache_core import get_redis_client
from django.db import transaction
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils.translation import ugettext as _, ugettext_lazy
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

    def get_error_message(self, form, field_name):
        return form[field_name].errors[0] if form[field_name].errors else None

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
        domain_has_default_gateway = SQLMobileBackend.get_domain_default_backend(
            SQLMobileBackend.SMS,
            self.domain,
            id_only=True
        ) is not None

        return {
            'outgoing_sms_form': TelerivetOutgoingSMSForm(),
            'test_sms_form': TelerivetPhoneNumberForm(),
            'finalize_gateway_form': FinalizeGatewaySetupForm(
                initial={
                    'set_as_default': (FinalizeGatewaySetupForm.NO
                                       if domain_has_default_gateway
                                       else FinalizeGatewaySetupForm.YES),
                }
            ),
            'webhook_url': absolute_reverse('telerivet_in'),
            'webhook_secret': webhook_secret,
            'request_token': request_token,
        }

    @property
    def unexpected_error(self):
        return _(
            "An unexpected error occurred. Please start over and if the "
            "problem persists, please report an issue."
        )

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

    def trim(self, value):
        if isinstance(value, basestring):
            return value.strip()

        return value

    @allow_remote_invocation
    def send_sample_sms(self, data):
        request_token = data.get('request_token')
        if not self.get_cached_webhook_secret(request_token):
            return {
                'success': False,
                'unexpected_error': self.unexpected_error,
            }

        outgoing_sms_form = TelerivetOutgoingSMSForm({
            'api_key': data.get('api_key'),
            'project_id': data.get('project_id'),
            'phone_id': data.get('phone_id'),
        })

        test_sms_form = TelerivetPhoneNumberForm({
            'test_phone_number': data.get('test_phone_number'),
        })

        # Be sure to call .is_valid() on both
        outgoing_sms_form_valid = outgoing_sms_form.is_valid()
        test_sms_form_valid = test_sms_form.is_valid()
        if not outgoing_sms_form_valid or not test_sms_form_valid:
            return {
                'success': False,
                'api_key_error': self.get_error_message(outgoing_sms_form, 'api_key'),
                'project_id_error': self.get_error_message(outgoing_sms_form, 'project_id'),
                'phone_id_error': self.get_error_message(outgoing_sms_form, 'phone_id'),
                'test_phone_number_error': self.get_error_message(test_sms_form, 'test_phone_number'),
            }

        tmp_backend = SQLTelerivetBackend()
        tmp_backend.set_extra_fields(
            api_key=outgoing_sms_form.cleaned_data.get('api_key'),
            project_id=outgoing_sms_form.cleaned_data.get('project_id'),
            phone_id=outgoing_sms_form.cleaned_data.get('phone_id'),
        )
        sms = SMS(
            phone_number=clean_phone_number(test_sms_form.cleaned_data.get('test_phone_number')),
            text="This is a test SMS from CommCareHQ."
        )
        tmp_backend.send(sms)
        return {
            'success': True,
        }

    @allow_remote_invocation
    def create_backend(self, data):
        webhook_secret = self.get_cached_webhook_secret(data.get('request_token'))
        values = {
            'name': data.get('name'),
            'description': _("My Telerivet Gateway '{}'").format(data.get('name')),
            'api_key': data.get('api_key'),
            'project_id': data.get('project_id'),
            'phone_id': data.get('phone_id'),
            'webhook_secret': webhook_secret,
        }
        form = TelerivetBackendForm(values, domain=self.domain, backend_id=None)
        if form.is_valid():
            with transaction.atomic():
                backend = SQLTelerivetBackend(
                    backend_type=SQLMobileBackend.SMS,
                    inbound_api_key=webhook_secret,
                    hq_api_id=SQLTelerivetBackend.get_api_id(),
                    is_global=False,
                    domain=self.domain,
                    name=form.cleaned_data.get('name'),
                    description=form.cleaned_data.get('description')
                )
                backend.set_extra_fields(
                    api_key=form.cleaned_data.get('api_key'),
                    project_id=form.cleaned_data.get('project_id'),
                    phone_id=form.cleaned_data.get('phone_id'),
                    webhook_secret=webhook_secret
                )
                backend.save()
                if data.get('set_as_default') == FinalizeGatewaySetupForm.YES:
                    SQLMobileBackendMapping.set_default_domain_backend(self.domain, backend)
                return {'success': True}

        name_error = self.get_error_message(form, 'name')
        return {
            'success': False,
            'name_error': name_error,
            'unexpected_error': None if name_error else self.unexpected_error,
        }

    @use_bootstrap3
    @use_angular_js
    def dispatch(self, *args, **kwargs):
        return super(TelerivetSetupView, self).dispatch(*args, **kwargs)
