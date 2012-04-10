from datetime import timedelta, datetime, time
import json
from django.core.urlresolvers import reverse
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponseRedirect, Http404, HttpResponse, HttpResponseBadRequest
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.reminders.forms import CaseReminderForm, ComplexCaseReminderForm
from corehq.apps.reminders.models import CaseReminderHandler, CaseReminderEvent, REPEAT_SCHEDULE_INDEFINITELY, EVENT_AS_OFFSET
from corehq.apps.users.models import CouchUser
from dimagi.utils.web import render_to_response
from dimagi.utils.parsing import string_to_datetime
from tropo import Tropo
from .models import UI_SIMPLE_FIXED, UI_COMPLEX

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
                handler.ui_type = UI_SIMPLE_FIXED
            for key, value in reminder_form.cleaned_data.items():
                if (key != "frequency") and (key != "message"):
                    handler[key] = value
            handler.max_iteration_count = REPEAT_SCHEDULE_INDEFINITELY
            handler.schedule_length = reminder_form.cleaned_data["frequency"]
            handler.event_interpretation = EVENT_AS_OFFSET
            handler.events = [
                CaseReminderEvent(
                    day_num = 0
                   ,fire_time = time(hour=0,minute=0,second=0)
                   ,message = reminder_form.cleaned_data["message"]
                   ,callback_timeout_intervals = []
               )
            ]
            handler.save()
            print handler.events[0].message
            return HttpResponseRedirect(reverse('list_reminders', args=[domain]))
    elif handler:
        initial = {}
        for key in handler.to_json():
            if (key != "max_iteration_count") and (key != "schedule_length") and (key != "events") and (key != "event_interpretation"):
                initial[key] = handler[key]
        initial["message"] = json.dumps(handler.events[0].message)
        initial["frequency"] = handler.schedule_length
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

@login_and_domain_required
def add_complex_reminder_schedule(request, domain, handler_id=None):
    if handler_id:
        h = CaseReminderHandler.get(handler_id)
        if h.doc_type != 'CaseReminderHandler' or h.domain != domain:
            raise Http404
    else:
        h = None
    
    if request.method == "POST":
        form = ComplexCaseReminderForm(request.POST)
        if form.is_valid():
            if h is None:
                h = CaseReminderHandler(domain=domain)
                h.ui_type = UI_COMPLEX
            h.case_type = form.cleaned_data["case_type"]
            h.nickname = form.cleaned_data["nickname"]
            h.default_lang = form.cleaned_data["default_lang"]
            h.method = form.cleaned_data["method"]
            h.recipient = form.cleaned_data["recipient"]
            h.start_property = form.cleaned_data["start_property"]
            h.start_value = form.cleaned_data["start_value"]
            h.start_date = form.cleaned_data["start_date"]
            h.start_offset = form.cleaned_data["start_offset"]
            h.start_match_type = form.cleaned_data["start_match_type"]
            h.schedule_length = form.cleaned_data["schedule_length"]
            h.event_interpretation = form.cleaned_data["event_interpretation"]
            h.max_iteration_count = form.cleaned_data["max_iteration_count"]
            h.until = form.cleaned_data["until"]
            h.events = form.cleaned_data["events"]
            h.save()
            return HttpResponseRedirect(reverse('list_reminders', args=[domain]))
    else:
        if h is not None:
            initial = {
                "case_type"             : h.case_type
               ,"nickname"              : h.nickname
               ,"default_lang"          : h.default_lang
               ,"method"                : h.method
               ,"recipient"             : h.recipient
               ,"start"                 : h.start
               ,"start_offset"          : h.start_offset
               ,"schedule_length"       : h.schedule_length
               ,"event_interpretation"  : h.event_interpretation
               ,"max_iteration_count"   : h.max_iteration_count
               ,"until"                 : h.until
               ,"events"                : h.events
            }
        else:
            initial = {}
        
        form = ComplexCaseReminderForm(initial=initial)
    
    return render_to_response(request, "reminders/partial/add_complex_reminder.html", {
        "domain":   domain
       ,"form":     form
    })



