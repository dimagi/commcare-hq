from datetime import timedelta, datetime
import json
from django.core.urlresolvers import reverse
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponseRedirect, Http404, HttpResponse, HttpResponseBadRequest
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.reminders.forms import CaseReminderForm
from corehq.apps.reminders.models import CaseReminderHandler, CaseReminderCallback
from corehq.apps.users.models import CouchUser
from dimagi.utils.web import render_to_response
from tropo import Tropo

@login_and_domain_required
def default(request, domain):
    return HttpResponseRedirect(reverse('list_reminders', args=[domain]))

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

@login_and_domain_required
def scheduled_reminders(request, domain, template="reminders/partial/scheduled_reminders.html"):
    reminders = CaseReminderHandler.get_all_reminders(domain)
    dates = []
    now = datetime.utcnow()
    today = now.date()
    if reminders:
        start_date = reminders[0].next_fire.date()
        if today < start_date:
            start_date = today
        end_date = reminders[-1].next_fire.date()
    else:
        start_date = end_date = today
    # make sure start date is a Monday and enddate is a Sunday
    start_date -= timedelta(days=start_date.weekday())
    end_date += timedelta(days=6-end_date.weekday())
    while start_date <= end_date:
        dates.append(start_date)
        start_date += timedelta(days=1)

    return render_to_response(request, template, {
        'domain': domain,
        'reminders': reminders,
        'dates': dates,
        'today': today,
        'now': now,
    })

@csrf_exempt
def callback(request, domain):
    if request.method == "POST":
        data = json.loads(request.raw_post_data)
        caller_id = data["session"]["from"]["id"]
        user = CouchUser.get_by_default_phone(caller_id)
        #
        c = CaseReminderCallback()
        c.phone_number = caller_id
        c.timestamp = datetime.utcnow()
        if user is not None:
            c.user_id = user._id
        c.save()
        #
        t = Tropo()
        t.reject()
        return HttpResponse(t.RenderJson())
    else:
        return HttpResponseBadRequest("Bad Request")

