import json
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, Http404
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.reminders.forms import CaseReminderForm
from corehq.apps.reminders.models import CaseReminderHandler
from dimagi.utils.web import render_to_response

@login_and_domain_required
def list_reminders(request, domain, template="reminders/partial/list_reminders.html"):
    handlers = CaseReminderHandler.get_handlers(domain=domain).all()
    print handlers
    return render_to_response(request, template, {
        'domain': domain,
        'reminder_handlers': handlers
    })

@login_and_domain_required
def add_reminder(request, domain, handler_id=None, template="reminders/partial/add_reminder.html"):

    if handler_id:
        handler = CaseReminderHandler.get(handler_id)
        if handler.doc_type != 'CaseReminderHandler' or handler.domain != domain:
            raise Http404
    else:
        handler = None
        
    if request.method == "POST":
        reminder_form = CaseReminderForm(request.POST)
        if reminder_form.is_valid():
            if not handler:
                handler = CaseReminderHandler(domain=domain)
            for key, value in reminder_form.cleaned_data.items():
                handler[key] = value
            handler.save()
            print handler.message
            return HttpResponseRedirect(reverse('list_reminders', args=[domain]))
    elif handler:
        initial = {}
        for key in handler.to_json():
            initial[key] = handler[key]
            if key == 'message':
                initial[key] = json.dumps(initial[key])
        reminder_form = CaseReminderForm(initial=initial)
    else:
        reminder_form = CaseReminderForm()

    return render_to_response(request, template, {
        'reminder_form': reminder_form,
        'domain': domain
    })

@login_and_domain_required
def delete_reminder(request, domain, handler_id):
    handler = CaseReminderHandler.get(handler_id)
    if handler.doc_type != 'CaseReminderHandler' or handler.domain != domain:
        raise Http404
    handler.retire()
    return HttpResponseRedirect(reverse('list_reminders', args=[domain]))
    