from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils.translation import ugettext_lazy
from djangular.views.mixins import JSONResponseMixin, allow_remote_invocation
from corehq.apps.sms.views import BaseMessagingSectionView
from corehq.apps.style.decorators import use_bootstrap3, use_angular_js
from corehq.messaging.smsbackends.telerivet.tasks import process_incoming_message
from corehq.messaging.smsbackends.telerivet.forms import (TelerivetOutgoingSMSForm,
    TelerivetPhoneNumberForm)


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

    @property
    def page_context(self):
        return {
            'outgoing_sms_form': TelerivetOutgoingSMSForm(),
            'test_sms_form': TelerivetPhoneNumberForm(),
        }

    @allow_remote_invocation
    def test(self):
        return {}

    @use_bootstrap3
    @use_angular_js
    def dispatch(self, *args, **kwargs):
        return super(TelerivetSetupView, self).dispatch(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        return HttpResponse()
