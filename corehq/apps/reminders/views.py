from datetime import timedelta, datetime, time
import json
from django.core.urlresolvers import reverse
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponseRedirect, Http404, HttpResponse, HttpResponseBadRequest
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.reminders.forms import CaseReminderForm, ComplexCaseReminderForm, SurveyForm, SurveySampleForm
from corehq.apps.reminders.models import CaseReminderHandler, CaseReminderEvent, REPEAT_SCHEDULE_INDEFINITELY, EVENT_AS_OFFSET, SurveyKeyword, Survey, SurveySample, SURVEY_METHOD_LIST
from corehq.apps.users.models import CouchUser, CommCareUser
from dimagi.utils.web import render_to_response
from dimagi.utils.parsing import string_to_datetime
from tropo import Tropo
from .models import UI_SIMPLE_FIXED, UI_COMPLEX
from .util import get_form_list, get_sample_list
from corehq.apps.app_manager.models import get_app, ApplicationBase

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
    
    form_list = get_form_list(domain)
    
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
               ,"start_property"        : h.start_property
               ,"start_value"           : h.start_value
               ,"start_date"            : h.start_date
               ,"start_match_type"      : h.start_match_type
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
        "domain":       domain
       ,"form":         form
       ,"form_list":    form_list
    })


@login_and_domain_required
def manage_surveys(request, domain):
    context = {
        "domain" : domain,
        "keywords" : SurveyKeyword.get_all(domain)
    }
    return render_to_response(request, "reminders/partial/manage_surveys.html", context)

@login_and_domain_required
def add_keyword(request, domain, keyword_id=None):
    if keyword_id is None:
        s = SurveyKeyword(domain = domain)
    else:
        s = SurveyKeyword.get(keyword_id)
    
    context = {
        "domain" : domain,
        "form_list" : get_form_list(domain),
        "errors" : [],
        "keyword" : s
    }
    
    if request.method == "GET":
        return render_to_response(request, "reminders/partial/add_keyword.html", context)
    else:
        keyword = request.POST.get("keyword", None)
        form_unique_id = request.POST.get("survey", None)
        
        if keyword is not None:
            keyword = keyword.strip()
        
        s.keyword = keyword
        s.form_unique_id = form_unique_id
        
        errors = []
        if keyword is None or keyword == "":
            errors.append("Please enter a keyword.")
        if form_unique_id is None:
            errors.append("Please create a form first, and then add a keyword for it.")
        duplicate_entry = SurveyKeyword.get_keyword(domain, keyword)
        if duplicate_entry is not None and keyword_id != duplicate_entry._id:
            errors.append("Keyword already exists.")
        
        if len(errors) > 0:
            context["errors"] = errors
            return render_to_response(request, "reminders/partial/add_keyword.html", context)
        else:
            s.save()
            return HttpResponseRedirect(reverse("manage_surveys", args=[domain]))

@login_and_domain_required
def delete_keyword(request, domain, keyword_id):
    s = SurveyKeyword.get(keyword_id)
    s.retire()
    return HttpResponseRedirect(reverse("manage_surveys", args=[domain]))

@login_and_domain_required
def add_survey(request, domain, survey_id=None):
    survey = None
    if survey_id is not None:
        survey = Survey.get(survey_id)
    
    if request.method == "POST":
        form = SurveyForm(request.POST)
        if form.is_valid():
            name                = form.cleaned_data.get("name")
            form_id             = form.cleaned_data.get("form_id")
            schedule_date       = form.cleaned_data.get("schedule_date")
            schedule_time       = form.cleaned_data.get("schedule_time")
            sample_id           = form.cleaned_data.get("sample_id")
            sample_name         = form.cleaned_data.get("sample_name")
            sample_contacts     = form.cleaned_data.get("sample_contacts")
            send_automatically  = form.cleaned_data.get("send_automatically")
            
            if sample_id == "--new--":
                sample = SurveySample (
                    domain = domain,
                    name = sample_name,
                    contacts = sample_contacts
                )
                sample.save()
            else:
                sample = SurveySample.get(sample_id)
                sample.name = sample_name
                sample.contacts = sample_contacts
                sample.save()
            
            if survey is None:
                survey = Survey (
                    domain = domain,
                    name = name,
                    form_unique_id = form_id,
                    sample_id = sample._id,
                    schedule_date = schedule_date,
                    schedule_time = schedule_time,
                    send_automatically = send_automatically
                )
            else:
                survey.name = name
                survey.form_unique_id = form_id
                survey.sample_id = sample._id
                survey.schedule_date = schedule_date
                survey.schedule_time = schedule_time
                survey.send_automatically = send_automatically
            survey.save()
            return HttpResponseRedirect(reverse("survey_list", args=[domain]))
    else:
        initial = {}
        if survey is not None:
            sample = SurveySample.get(survey.sample_id)
            initial["name"] = survey.name
            initial["form_id"] = survey.form_unique_id
            initial["sample_id"] = survey.sample_id
            initial["schedule_date"] = survey.schedule_date
            initial["schedule_time"] = survey.schedule_time
            initial["sample_name"] = sample.name
            initial["sample_contacts"] = sample.contacts
            initial["send_automatically"] = survey.send_automatically
        form = SurveyForm(initial=initial)
    
    form_list = get_form_list(domain)
    form_list.insert(0, {"code":"--choose--", "name":"-- Choose --"})
    sample_list = get_sample_list(domain)
    sample_list.insert(0, {"code":"--new--", "name":"-- Create New Sample --"})
    
    context = {
        "domain" : domain,
        "survey_id" : survey_id,
        "form" : form,
        "form_list" : form_list,
        "sample_list" : sample_list,
        "method_list" : SURVEY_METHOD_LIST,
        "user_list" : CommCareUser.by_domain(domain),
    }
    return render_to_response(request, "reminders/partial/add_survey.html", context)

@login_and_domain_required
def survey_list(request, domain):
    context = {
        "domain" : domain,
        "surveys" : Survey.get_all(domain)
    }
    return render_to_response(request, "reminders/partial/survey_list.html", context)

@login_and_domain_required
def add_sample(request, domain, sample_id=None):
    sample = None
    if sample_id is not None:
        sample = SurveySample.get(sample_id)
    
    if request.method == "POST":
        form = SurveySampleForm(request.POST)
        if form.is_valid():
            name            = form.cleaned_data.get("name")
            sample_contacts = form.cleaned_data.get("sample_contacts")
            
            if sample is None:
                sample = SurveySample (
                    domain = domain,
                    name = name,
                    contacts = sample_contacts
                )
            else:
                sample.name = name
                sample.contacts = sample_contacts
            sample.save()
            return HttpResponseRedirect(reverse("sample_list", args=[domain]))
    else:
        initial = {}
        if sample is not None:
            initial["name"] = sample.name
            initial["sample_contacts"] = sample.contacts
        form = SurveySampleForm(initial=initial)
    
    context = {
        "domain" : domain,
        "form" : form,
        "sample_id" : sample_id
    }
    return render_to_response(request, "reminders/partial/add_sample.html", context)

@login_and_domain_required
def sample_list(request, domain):
    context = {
        "domain" : domain,
        "samples" : SurveySample.get_all(domain)
    }
    return render_to_response(request, "reminders/partial/sample_list.html", context)

