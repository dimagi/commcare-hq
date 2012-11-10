from datetime import timedelta, datetime, time
import json
from django.core.urlresolvers import reverse
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponseRedirect, Http404, HttpResponse, HttpResponseBadRequest
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.reminders.forms import CaseReminderForm, ComplexCaseReminderForm, SurveyForm, SurveySampleForm
from corehq.apps.reminders.models import CaseReminderHandler, CaseReminderEvent, REPEAT_SCHEDULE_INDEFINITELY, EVENT_AS_OFFSET, EVENT_AS_SCHEDULE, SurveyKeyword, Survey, SurveySample, SURVEY_METHOD_LIST, SurveyWave, ON_DATETIME, RECIPIENT_SURVEY_SAMPLE
from corehq.apps.users.models import CouchUser, CommCareUser
from dimagi.utils.web import render_to_response
from dimagi.utils.parsing import string_to_datetime
from tropo import Tropo
from .models import UI_SIMPLE_FIXED, UI_COMPLEX
from .util import get_form_list, get_sample_list
from corehq.apps.app_manager.models import get_app, ApplicationBase
from corehq.apps.sms.mixin import VerifiedNumber
from corehq.apps.sms.util import register_sms_contact
from corehq.apps.domain.models import DomainCounter
from casexml.apps.case.models import CommCareCase
from dateutil.parser import parse

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
    sample_list = get_sample_list(domain)
    
    if request.method == "POST":
        form = ComplexCaseReminderForm(request.POST)
        if form.is_valid():
            if h is None:
                h = CaseReminderHandler(domain=domain)
                h.ui_type = UI_COMPLEX
            else:
                if h.start_condition_type != form.cleaned_data["start_condition_type"]:
                    for reminder in h.get_reminders():
                        reminder.retire()
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
            h.submit_partial_forms = form.cleaned_data["submit_partial_forms"]
            h.ui_frequency = form.cleaned_data["frequency"]
            h.start_condition_type = form.cleaned_data["start_condition_type"]
            if form.cleaned_data["start_condition_type"] == "ON_DATETIME":
                dt = parse(form.cleaned_data["start_datetime_date"]).date()
                tm = parse(form.cleaned_data["start_datetime_time"]).time()
                h.start_datetime = datetime.combine(dt, tm)
            else:
                h.start_datetime = None
            h.sample_id = form.cleaned_data["sample_id"]
            h.save()
            return HttpResponseRedirect(reverse('list_reminders', args=[domain]))
    else:
        if h is not None:
            initial = {
                "case_type"             : h.case_type,
                "nickname"              : h.nickname,
                "default_lang"          : h.default_lang,
                "method"                : h.method,
                "recipient"             : h.recipient,
                "start_property"        : h.start_property,
                "start_value"           : h.start_value,
                "start_date"            : h.start_date,
                "start_match_type"      : h.start_match_type,
                "start_offset"          : h.start_offset,
                "schedule_length"       : h.schedule_length,
                "event_interpretation"  : h.event_interpretation,
                "max_iteration_count"   : h.max_iteration_count,
                "until"                 : h.until,
                "events"                : h.events,
                "submit_partial_forms"  : h.submit_partial_forms,
                "start_condition_type"  : h.start_condition_type,
                "start_datetime_date"   : str(h.start_datetime.date()) if isinstance(h.start_datetime, datetime) else None,
                "start_datetime_time"   : str(h.start_datetime.time()) if isinstance(h.start_datetime, datetime) else None,
                "frequency"             : h.ui_frequency,
                "sample_id"             : h.sample_id,
                "use_until"             : "Y" if h.until is not None else "N"
            }
        else:
            initial = {
                "events"    : [CaseReminderEvent(day_num=0, fire_time=time(0,0), message={"":""}, callback_timeout_intervals=[], form_unique_id=None)],
            }
        
        form = ComplexCaseReminderForm(initial=initial)
    
    return render_to_response(request, "reminders/partial/add_complex_reminder.html", {
        "domain":       domain,
        "form":         form,
        "form_list":    form_list,
        "handler_id":   handler_id,
        "sample_list":  sample_list,
    })


@login_and_domain_required
def manage_keywords(request, domain):
    context = {
        "domain" : domain,
        "keywords" : SurveyKeyword.get_all(domain)
    }
    return render_to_response(request, "reminders/partial/manage_keywords.html", context)

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
            return HttpResponseRedirect(reverse("manage_keywords", args=[domain]))

@login_and_domain_required
def delete_keyword(request, domain, keyword_id):
    s = SurveyKeyword.get(keyword_id)
    s.retire()
    return HttpResponseRedirect(reverse("manage_keywords", args=[domain]))

@login_and_domain_required
def add_survey(request, domain, survey_id=None):
    survey = None
    if survey_id is not None:
        survey = Survey.get(survey_id)
    
    if request.method == "POST":
        form = SurveyForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data.get("name")
            waves = form.cleaned_data.get("waves")
            followups = form.cleaned_data.get("followups")
            samples = form.cleaned_data.get("samples")
            send_automatically = form.cleaned_data.get("send_automatically")
            send_followup = form.cleaned_data.get("send_followup")
            
            if send_followup:
                timeout_intervals = [int(followup["interval"]) * 1440 for followup in followups]
            else:
                timeout_intervals = []
            
            if survey is None:
                wave_list = []
                for wave in waves:
                    wave_list.append(SurveyWave(date=parse(wave["date"]).date(), time=parse(wave["time"]).time(), form_id=wave["form_id"], reminder_definitions={}))
                
                if send_automatically:
                    for wave in wave_list:
                        for sample in samples:
                            if sample["method"] == "SMS":
                                handler = CaseReminderHandler(
                                    domain = domain,
                                    nickname = "",
                                    default_lang = "en",
                                    method = "survey",
                                    recipient = RECIPIENT_SURVEY_SAMPLE,
                                    start_condition_type = ON_DATETIME,
                                    start_datetime = datetime.combine(wave.date, time(0,0)),
                                    start_offset = 0,
                                    events = [CaseReminderEvent(
                                        day_num = 0,
                                        fire_time = wave.time,
                                        form_unique_id = wave.form_id,
                                        callback_timeout_intervals = timeout_intervals
                                    )],
                                    schedule_length = 1,
                                    event_interpretation = EVENT_AS_SCHEDULE,
                                    max_iteration_count = 1,
                                    sample_id = sample["sample_id"]
                                )
                                handler.save()
                                wave.reminder_definitions[sample["sample_id"]] = handler._id
                
                survey = Survey (
                    domain = domain,
                    name = name,
                    waves = wave_list,
                    followups = followups,
                    samples = samples,
                    send_automatically = send_automatically,
                    send_followup = send_followup
                )
            else:
                current_waves = survey.waves
                survey.waves = []
                unchanged_wave_json = []
                
                # Keep any waves that didn't change in case the surveys are in progress
                for wave in current_waves:
                    for wave_json in waves:
                        parsed_date = parse(wave_json["date"]).date()
                        parsed_time = parse(wave_json["time"]).time()
                        if parsed_date == wave.date and parsed_time == wave.time and wave_json["form_id"] == wave.form_id:
                            survey.waves.append(wave)
                            unchanged_wave_json.append(wave_json)
                            continue
                
                for wave in survey.waves:
                    current_waves.remove(wave)
                
                for wave_json in unchanged_wave_json:
                    waves.remove(wave_json)
                
                # Retire reminder definitions for old waves
                for wave in current_waves:
                    for sample_id, handler_id in wave.reminder_definitions.items():
                        handler = CaseReminderHandler.get(handler_id)
                        handler.retire()
                
                # Add in new waves
                for wave_json in waves:
                    survey.waves.append(SurveyWave(
                        date=parse(wave_json["date"]).date(),
                        time=parse(wave_json["time"]).time(),
                        form_id=wave_json["form_id"],
                        reminder_definitions={},
                    ))
                
                # Retire reminder definitions that are no longer needed
                if send_automatically:
                    new_sample_ids = [sample_json["sample_id"] for sample_json in samples if sample_json["method"] == "SMS"]
                else:
                    new_sample_ids = []
                
                for wave in survey.waves:
                    for sample_id, handler_id in wave.reminder_definitions.items():
                        if sample_id not in new_sample_ids:
                            handler = CaseReminderHandler.get(handler_id)
                            handler.retire()
                            del wave.reminder_definitions[sample_id]
                
                # Update existing reminder definitions
                for wave in survey.waves:
                    for sample_id, handler_id in wave.reminder_definitions.items():
                        handler = CaseReminderHandler.get(handler_id)
                        handler.events[0].callback_timeout_intervals = timeout_intervals
                        handler.save()
                
                # Create additional reminder definitions as necessary
                for wave in survey.waves:
                    for sample_id in new_sample_ids:
                        if sample_id not in wave.reminder_definitions:
                            handler = CaseReminderHandler(
                                domain = domain,
                                nickname = "",
                                default_lang = "en",
                                method = "survey",
                                recipient = RECIPIENT_SURVEY_SAMPLE,
                                start_condition_type = ON_DATETIME,
                                start_datetime = datetime.combine(wave.date, time(0,0)),
                                start_offset = 0,
                                events = [CaseReminderEvent(
                                    day_num = 0,
                                    fire_time = wave.time,
                                    form_unique_id = wave.form_id,
                                    callback_timeout_intervals = timeout_intervals
                                )],
                                schedule_length = 1,
                                event_interpretation = EVENT_AS_SCHEDULE,
                                max_iteration_count = 1,
                                sample_id = sample_id
                            )
                            handler.save()
                            wave.reminder_definitions[sample_id] = handler._id
                
                # Set the rest of the survey info
                survey.name = name
                survey.followups = followups
                survey.samples = samples
                survey.send_automatically = send_automatically
                survey.send_followup = send_followup
            
            # Sort the questionnaire waves by date and time (for display purposes only)
            survey.waves = sorted(survey.waves, key = lambda wave : datetime.combine(wave.date, wave.time))
            
            # Create / Close delegation tasks as necessary for samples with method "CATI"
            survey.update_delegation_tasks(request.couch_user.get_id)
            
            survey.save()
            return HttpResponseRedirect(reverse("survey_list", args=[domain]))
    else:
        initial = {}
        if survey is not None:
            waves = []
            samples = [SurveySample.get(sample["sample_id"]) for sample in survey.samples]
            utcnow = datetime.utcnow()
            for wave in survey.waves:
                wave_json = {
                    "date" : str(wave.date),
                    "form_id" : wave.form_id,
                    "time" : str(wave.time),
                    "ignore" : False,
                }
                
                for sample in samples:
                    if CaseReminderHandler.timestamp_to_utc(sample, datetime.combine(wave.date, wave.time)) < utcnow:
                        wave_json["ignore"] = True
                        break
                
                waves.append(wave_json)
            
            initial["name"] = survey.name
            initial["waves"] = waves
            initial["followups"] = survey.followups
            initial["samples"] = survey.samples
            initial["send_automatically"] = survey.send_automatically
            initial["send_followup"] = survey.send_followup
            
        form = SurveyForm(initial=initial)
    
    form_list = get_form_list(domain)
    form_list.insert(0, {"code":"--choose--", "name":"-- Choose --"})
    sample_list = get_sample_list(domain)
    sample_list.insert(0, {"code":"--choose--", "name":"-- Choose --"})
    
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
            time_zone       = form.cleaned_data.get("time_zone")
            
            if sample is None:
                sample = SurveySample (
                    domain = domain,
                    name = name,
                    time_zone = time_zone.zone
                )
            else:
                sample.name = name
                sample.time_zone = time_zone.zone
            
            phone_numbers = []
            for contact in sample_contacts:
                phone_numbers.append(contact["phone_number"])
            
            existing_number_entries = VerifiedNumber.view('sms/verified_number_by_number',
                                            keys=phone_numbers,
                                            include_docs=True
                                       ).all()
            
            existing_numbers = [v.phone_number for v in existing_number_entries]
            nonexisting_numbers = list(set(phone_numbers).difference(existing_numbers))
            
            id_range = DomainCounter.increment(domain, "survey_contact_id", len(nonexisting_numbers))
            ids = iter(range(id_range[0], id_range[1] + 1))
            for phone_number in nonexisting_numbers:
                register_sms_contact(domain, "participant", str(ids.next()), request.couch_user.get_id, phone_number, contact_phone_number_is_verified="1", contact_backend_id="MOBILE_BACKEND_TROPO_US", language_code="en", time_zone=time_zone.zone)
            
            newly_registered_entries = VerifiedNumber.view('sms/verified_number_by_number',
                                            keys=nonexisting_numbers,
                                            include_docs=True
                                       ).all()
            
            sample.contacts = [v.owner_id for v in existing_number_entries] + [v.owner_id for v in newly_registered_entries]
            
            sample.save()
            
            # Update delegation tasks for surveys using this sample
            surveys = Survey.view("reminders/sample_to_survey", key=[domain, sample._id, "CATI"], include_docs=True).all()
            for survey in surveys:
                survey.update_delegation_tasks(request.couch_user.get_id)
                survey.save()
            
            return HttpResponseRedirect(reverse("sample_list", args=[domain]))
    else:
        initial = {}
        if sample is not None:
            initial["name"] = sample.name
            initial["time_zone"] = sample.time_zone
            contact_info = []
            for case_id in sample.contacts:
                case = CommCareCase.get(case_id)
                contact_info.append({"id":case.name, "phone_number":case.contact_phone_number})
            initial["sample_contacts"] = contact_info
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

