from custom.fri.forms import MessageBankForm
from custom.fri.reports.reports import MessageBankReport
from custom.fri.api import get_message_bank
from custom.fri.models import FRIMessageBankMessage
from corehq.apps.reports.dispatcher import CustomProjectReportDispatcher
from corehq.apps.domain.decorators import require_previewer, login_and_domain_required
from django.http import HttpResponseRedirect, Http404
from django.core.urlresolvers import reverse
from django.contrib import messages
from django.utils.translation import ugettext as _, ugettext_noop

@require_previewer
@login_and_domain_required
def upload_message_bank(request, domain):
    if request.method == "POST":
        form = MessageBankForm(request.POST, request.FILES)
        if form.is_valid():
            current_bank = get_message_bank(domain)
            message_id_map = {}
            for message in current_bank:
                message_id_map[message.fri_id.upper()] = message

            # The message bank is supposed to be static, and is intended
            # to be a one-time upload. So to prevent any issues with
            # overwriting messages or deleting messages by accident, this
            # api will only add new messages to the message bank.
            # If more specialized functionality is needed later on, a new
            # UI should be built.
            for message in form.cleaned_data["message_bank_file"]:
                msg_id = message["msg_id"]
                text = message["text"]
                if msg_id.upper() not in message_id_map:
                    msg = FRIMessageBankMessage(
                        domain = domain,
                        risk_profile = msg_id[0].upper(),
                        message = text,
                        fri_id = msg_id,
                    )
                    msg.save()
            messages.success(request, _("Message Bank Uploaded."))
        else:
            messages.error(request, form._errors["message_bank_file"].as_text())
    else:
        messages.error(request, _("ERROR: POST Expected."))
    return HttpResponseRedirect(reverse(CustomProjectReportDispatcher.name(), args=[domain, MessageBankReport.slug]))

