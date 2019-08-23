import csv342 as csv

from django.http import HttpResponseRedirect
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.utils.translation import ugettext as _

from corehq.apps.domain.utils import send_repeater_payloads
from corehq.apps.users.decorators import require_can_edit_web_users


@require_POST
@require_can_edit_web_users
def generate_repeater_payloads(request, domain):
    try:
        email_id = request.POST.get('email_id')
        repeater_id = request.POST.get('repeater_id')
        data = csv.reader(request.FILES['payload_ids_file'])
        payload_ids = [row[0] for row in data]
    except Exception as e:
        messages.error(request, _("Could not process the file. %s") % str(e))
    else:
        send_repeater_payloads.delay(repeater_id, payload_ids, email_id)
        messages.success(request, _("Successfully queued request. You should receive an email shortly."))
    return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))
