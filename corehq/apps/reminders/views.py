from datetime import timedelta, datetime, time
import json
from couchdbkit import ResourceNotFound
from django.contrib import messages
from django.utils.decorators import method_decorator
import pytz
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, Http404, HttpResponse
from django.shortcuts import render
from corehq.apps.casegroups.dbaccessors import get_case_groups_in_domain
from corehq.apps.casegroups.models import CommCareCaseGroup
from corehq.apps.translations.models import StandaloneTranslationDoc
from corehq.const import SERVER_DATETIME_FORMAT
from corehq.util.timezones.conversions import ServerTime
from dimagi.utils.couch.cache.cache_core import get_redis_client
from dimagi.utils.couch import CriticalSection
from django.utils.translation import ugettext as _, ugettext_noop
from corehq import privileges
from corehq.apps.accounting.decorators import requires_privilege_with_fallback
from corehq.apps.app_manager.models import Application, Form
from corehq.apps.app_manager.util import (get_case_properties,
    get_correct_app_class)
from corehq.apps.hqwebapp.views import CRUDPaginatedViewMixin
from dimagi.utils.logging import notify_exception

from corehq.apps.reminders.forms import (
    SurveyForm,
    SurveySampleForm,
    EditContactForm,
    RemindersInErrorForm,
    OneTimeReminderForm,
    SimpleScheduleCaseReminderForm,
    CaseReminderEventForm,
    CaseReminderEventMessageForm,
    ComplexScheduleCaseReminderForm,
    KeywordForm,
    NO_RESPONSE,
)
from corehq.apps.reminders.models import (
    CaseReminderHandler,
    CaseReminderEvent,
    CaseReminder,
    REPEAT_SCHEDULE_INDEFINITELY,
    EVENT_AS_OFFSET,
    EVENT_AS_SCHEDULE,
    SurveyKeyword,
    SurveyKeywordAction,
    Survey,
    SURVEY_METHOD_LIST,
    SurveyWave,
    ON_DATETIME,
    RECIPIENT_SURVEY_SAMPLE,
    QUESTION_RETRY_CHOICES,
    REMINDER_TYPE_ONE_TIME,
    REMINDER_TYPE_DEFAULT,
    REMINDER_TYPE_SURVEY_MANAGEMENT,
    SEND_NOW, SEND_LATER,
    METHOD_SMS,
    METHOD_SMS_SURVEY,
    METHOD_STRUCTURED_SMS,
    RECIPIENT_USER_GROUP,
    RECIPIENT_SENDER,
    METHOD_IVR_SURVEY,
    get_events_scheduling_info,
)
from corehq.apps.sms.views import BaseMessagingSectionView
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import CommCareUser, Permissions
from dimagi.utils.decorators.memoized import memoized
from .models import UI_SIMPLE_FIXED, UI_COMPLEX
from .util import get_form_list, get_sample_list, get_recipient_name, get_form_name, can_use_survey_reminders
from corehq.apps.sms.mixin import VerifiedNumber
from corehq.apps.sms.util import register_sms_contact, update_contact
from corehq.apps.domain.models import Domain, DomainCounter
from corehq.apps.groups.models import Group
from casexml.apps.case.models import CommCareCase
from dateutil.parser import parse
from corehq.apps.sms.util import close_task
from corehq.util.timezones.utils import get_timezone_for_user
from dimagi.utils.couch.database import is_bigcouch, bigcouch_quorum_count, iter_docs

ACTION_ACTIVATE = 'activate'
ACTION_DEACTIVATE = 'deactivate'
ACTION_DELETE = 'delete'

reminders_framework_permission = lambda *args, **kwargs: (
    require_permission(Permissions.edit_data)(
        requires_privilege_with_fallback(privileges.REMINDERS_FRAMEWORK)(*args, **kwargs)
    )
)

survey_reminders_permission = lambda *args, **kwargs: (
    require_permission(Permissions.edit_data)(
        requires_privilege_with_fallback(privileges.INBOUND_SMS)(*args, **kwargs)
    )
)

def get_project_time_info(domain):
    timezone = get_timezone_for_user(None, domain)
    now = pytz.utc.localize(datetime.utcnow())
    timezone_now = now.astimezone(timezone)
    return (timezone, now, timezone_now)


@reminders_framework_permission
def list_reminders(request, domain, reminder_type=REMINDER_TYPE_DEFAULT):
    # We need to keep this until the broadcast ui gets updated
    all_handlers = CaseReminderHandler.get_handlers(domain)
    all_handlers = filter(lambda x : x.reminder_type == reminder_type, all_handlers)
    if reminder_type == REMINDER_TYPE_ONE_TIME:
        all_handlers.sort(key=lambda handler : handler.start_datetime)

    if not can_use_survey_reminders(request):
        all_handlers = filter(
            lambda x: x.method not in [METHOD_IVR_SURVEY, METHOD_SMS_SURVEY],
            all_handlers
        )

    handlers = []
    utcnow = datetime.utcnow()
    timezone, now, timezone_now = get_project_time_info(domain)
    for handler in all_handlers:
        if reminder_type == REMINDER_TYPE_ONE_TIME:
            reminders = handler.get_reminders()
            try:
                reminder = reminders[0]
            except IndexError:
                handler.retire()
                continue
            recipients = get_recipient_name(reminder.recipient, include_desc=False)
            
            if handler.method == METHOD_SMS_SURVEY:
                content = get_form_name(handler.events[0].form_unique_id)
            else:
                message = handler.events[0].message[handler.default_lang]
                if len(message) > 50:
                    content = '"%s..."' % message[:47]
                else:
                    content = '"%s"' % message
            
            sent = handler.start_datetime <= utcnow
        else:
            recipients = None
            content = None
            sent = None
        
        handlers.append({
            "handler" : handler,
            "recipients" : recipients,
            "content" : content,
            "sent" : sent,
            "start_datetime" : ServerTime(handler.start_datetime).user_time(timezone).done() if handler.start_datetime is not None else None,
        })
    
    return render(request, "reminders/list_broadcasts.html", {
        'domain': domain,
        'reminder_handlers': handlers,
        'reminder_type': reminder_type,
        'timezone' : timezone,
        'now' : now,
        'timezone_now' : timezone_now,
    })


def render_one_time_reminder_form(request, domain, form, handler_id):
    timezone, now, timezone_now = get_project_time_info(domain)

    context = {
        "domain": domain,
        "form" : form,
        "sample_list" : get_sample_list(domain),
        "form_list" : get_form_list(domain),
        "groups" : Group.by_domain(domain),
        "handler_id" : handler_id,
        "timezone" : timezone,
        "timezone_now" : timezone_now,
        "now" : now,
    }

    return render(request, "reminders/partial/add_one_time_reminder.html", context)

@reminders_framework_permission
def add_one_time_reminder(request, domain, handler_id=None):
    if handler_id:
        handler = CaseReminderHandler.get(handler_id)
        if handler.doc_type != "CaseReminderHandler" or handler.domain != domain:
            raise Http404
    else:
        handler = None

    timezone = get_timezone_for_user(None, domain) # Use project timezone only

    if request.method == "POST":
        form = OneTimeReminderForm(request.POST, can_use_survey=can_use_survey_reminders(request))
        form._cchq_domain = domain
        if form.is_valid():
            content_type = form.cleaned_data.get("content_type")
            recipient_type = form.cleaned_data.get("recipient_type")

            if handler is None:
                handler = CaseReminderHandler(
                    domain = domain,
                    reminder_type = REMINDER_TYPE_ONE_TIME,
                    nickname = "One-time Reminder",
                )
            handler.default_lang = "xx"
            handler.method = content_type
            handler.recipient = recipient_type
            handler.start_condition_type = ON_DATETIME
            handler.start_datetime = form.cleaned_data.get("datetime")
            handler.start_offset = 0
            handler.events = [CaseReminderEvent(
                day_num = 0,
                fire_time = time(0,0),
                form_unique_id = form.cleaned_data.get("form_unique_id") if content_type == METHOD_SMS_SURVEY else None,
                message = {handler.default_lang : form.cleaned_data.get("message")} if content_type == METHOD_SMS else {},
                callback_timeout_intervals = [],
            )]
            handler.schedule_length = 1
            handler.event_interpretation = EVENT_AS_OFFSET
            handler.max_iteration_count = 1
            handler.sample_id = form.cleaned_data.get("case_group_id") if recipient_type == RECIPIENT_SURVEY_SAMPLE else None
            handler.user_group_id = form.cleaned_data.get("user_group_id") if recipient_type == RECIPIENT_USER_GROUP else None
            handler.save()
            return HttpResponseRedirect(reverse('one_time_reminders', args=[domain]))
    else:
        if handler is not None:
            start_date_user_time = (ServerTime(handler.start_datetime)
                                    .user_time(timezone))
            initial = {
                "send_type": SEND_LATER,
                "date": start_date_user_time.ui_string("%Y-%m-%d"),
                "time": start_date_user_time.ui_string("%H:%M"),
                "recipient_type": handler.recipient,
                "case_group_id": handler.sample_id,
                "user_group_id": handler.user_group_id,
                "content_type": handler.method,
                "message": (
                    handler.events[0].message[handler.default_lang]
                    if handler.default_lang in handler.events[0].message
                    else None
                ),
                "form_unique_id": (
                    handler.events[0].form_unique_id
                    if handler.events[0].form_unique_id is not None
                    else None
                ),
            }
        else:
            initial = {}

        form = OneTimeReminderForm(initial=initial, can_use_survey=can_use_survey_reminders(request))

    return render_one_time_reminder_form(request, domain, form, handler_id)

@reminders_framework_permission
def copy_one_time_reminder(request, domain, handler_id):
    handler = CaseReminderHandler.get(handler_id)
    initial = {
        "send_type" : SEND_NOW,
        "recipient_type" : handler.recipient,
        "case_group_id" : handler.sample_id,
        "user_group_id" : handler.user_group_id,
        "content_type" : handler.method,
        "message" : handler.events[0].message[handler.default_lang] if handler.default_lang in handler.events[0].message else None,
        "form_unique_id" : handler.events[0].form_unique_id if handler.events[0].form_unique_id is not None else None,
    }
    form = OneTimeReminderForm(initial=initial,
        can_use_survey=can_use_survey_reminders(request))
    return render_one_time_reminder_form(request, domain, form, None)

@reminders_framework_permission
def delete_reminder(request, domain, handler_id):
    # We need to keep this until the broadcast ui gets updated
    handler = CaseReminderHandler.get(handler_id)
    if handler.doc_type != 'CaseReminderHandler' or handler.domain != domain:
        raise Http404
    if handler.locked:
        messages.error(request, _("Please wait until the rule finishes "
            "processing before making further changes."))
        return HttpResponseRedirect(reverse('list_reminders', args=[domain]))
    handler.retire()
    view_name = "one_time_reminders" if handler.reminder_type == REMINDER_TYPE_ONE_TIME else "list_reminders"
    return HttpResponseRedirect(reverse(view_name, args=[domain]))


@reminders_framework_permission
def scheduled_reminders(request, domain, template="reminders/partial/scheduled_reminders.html"):
    timezone = Domain.get_by_name(domain).get_default_timezone()
    reminders = CaseReminderHandler.get_all_reminders(domain)
    dates = []
    now = datetime.utcnow()
    timezone_now = datetime.now(timezone)
    today = timezone_now.date()

    def adjust_next_fire_to_timezone(reminder_utc):
        return ServerTime(reminder_utc.next_fire).user_time(timezone).done()

    if reminders:
        start_date = adjust_next_fire_to_timezone(reminders[0]).date()
        if today < start_date:
            start_date = today
        end_date = adjust_next_fire_to_timezone(reminders[-1]).date()
    else:
        start_date = end_date = today
    # make sure start date is a Monday and enddate is a Sunday
    start_date -= timedelta(days=start_date.weekday())
    end_date += timedelta(days=6-end_date.weekday())
    while start_date <= end_date:
        dates.append(start_date)
        start_date += timedelta(days=1)
    
    reminder_data = []
    for reminder in reminders:
        handler = reminder.handler
        recipient = reminder.recipient
        recipient_desc = get_recipient_name(recipient)
        case = reminder.case
        
        reminder_data.append({
            "handler_name" : handler.nickname,
            "next_fire" : adjust_next_fire_to_timezone(reminder),
            "recipient_desc" : recipient_desc,
            "recipient_type" : handler.recipient,
            "case_id" : case.get_id if case is not None else None,
            "case_name" : case.name if case is not None else None,
        })
    
    return render(request, template, {
        'domain': domain,
        'reminder_data': reminder_data,
        'dates': dates,
        'today': today,
        'now': now,
        'timezone': timezone,
        'timezone_now': timezone_now,
    })


class CreateScheduledReminderView(BaseMessagingSectionView):
    urlname = 'create_reminder_schedule'
    page_title = ugettext_noop("Schedule Reminder")
    template_name = 'reminders/manage_scheduled_reminder.html'
    ui_type = UI_SIMPLE_FIXED

    @property
    def reminder_form_class(self):
        return {
            UI_COMPLEX: ComplexScheduleCaseReminderForm,
            UI_SIMPLE_FIXED: SimpleScheduleCaseReminderForm,
        }[self.ui_type]

    @property
    @memoized
    def schedule_form(self):
        if self.request.method == 'POST':
            return self.reminder_form_class(
                self.request.POST,
                domain=self.domain,
                is_previewer=self.is_previewer,
                can_use_survey=can_use_survey_reminders(self.request),
                available_languages=self.available_languages,
            )
        return self.reminder_form_class(
            is_previewer=self.is_previewer,
            domain=self.domain,
            can_use_survey=can_use_survey_reminders(self.request),
            available_languages=self.available_languages,
        )

    @property
    def available_languages(self):
        """
        Returns a the list of language codes available for the domain, or
        [] if no languages are specified.
        """
        translation_doc = StandaloneTranslationDoc.get_obj(self.domain, "sms")
        if translation_doc and translation_doc.langs:
            return translation_doc.langs
        return []

    @property
    def is_previewer(self):
        return self.request.couch_user.is_previewer()

    @property
    def parent_pages(self):
        return [
            {
                'title': _("Reminders"),
                'url': reverse(RemindersListView.urlname, args=[self.domain]),
            },
        ]

    @property
    def page_context(self):
        return {
            'form': self.schedule_form,
            'event_form': CaseReminderEventForm(ui_type=self.ui_type),
            'message_form': CaseReminderEventMessageForm(),
            'ui_type': self.ui_type,
            'available_languages': self.available_languages,
        }

    @property
    def available_case_types(self):
        case_types = []
        for app in self.apps:
            case_types.extend([m.case_type for m in app.modules])
        return set(case_types)

    @property
    def action(self):
        return self.request.POST.get('action')

    @property
    def case_type(self):
        return self.request.POST.get('caseType')

    @property
    def app_ids(self):
        data = Application.get_db().view(
            'app_manager/applications_brief',
            reduce=False,
            startkey=[self.domain],
            endkey=[self.domain, {}],
        ).all()
        return [d['id'] for d in data]

    @property
    @memoized
    def apps(self):
        result = []
        for app_doc in iter_docs(Application.get_db(), self.app_ids):
            app = get_correct_app_class(app_doc).wrap(app_doc)
            if not app.is_remote_app():
                result.append(app)
        return result

    @property
    def search_term(self):
        return self.request.POST.get('term')

    @property
    def search_case_type_response(self):
        return list(self.available_case_types)

    def clean_dict_list(self, dict_list):
        """
        Takes a dict of {string: list} and returns the same result, only
        removing any duplicate entries in each of the lists.
        """
        result = {}
        for key in dict_list:
            result[key] = list(set(dict_list[key]))
        return result

    @property
    def search_form_by_id_response(self):
        """
        Returns a dict of {"id": [form unique id], "text": [full form path]}
        """
        form_unique_id = self.search_term
        try:
            form = Form.get_form(form_unique_id)
            assert form.get_app().domain == self.domain
            return {
                'text': form.full_path_name,
                'id': form_unique_id,
            }
        except:
            return {}

    @property
    def search_case_property_response(self):
        """
        Returns a dict of {case type: [case properties...]}
        """
        result = {}
        for app in self.apps:
            case_types = list(set([m.case_type for m in app.modules]))
            for case_type in case_types:
                if case_type not in result:
                    result[case_type] = ['name']
                for properties in get_case_properties(app, [case_type]).values():
                    result[case_type].extend(properties)
        return self.clean_dict_list(result)

    def get_parent_child_types(self):
        """
        Returns a dict of {parent case type: [subcase types...]}
        """
        parent_child_types = {}
        for app in self.apps:
            for module in app.get_modules():
                case_type = module.case_type
                if case_type not in parent_child_types:
                    parent_child_types[case_type] = []
                if module.module_type == 'basic':
                    for form in module.get_forms():
                        for subcase in form.actions.subcases:
                            parent_child_types[case_type].append(subcase.case_type)
                elif module.module_type == 'advanced':
                    for form in module.get_forms():
                        for subcase in form.actions.get_open_subcase_actions(case_type):
                            parent_child_types[case_type].append(subcase.case_type)
        return self.clean_dict_list(parent_child_types)

    @property
    def search_subcase_property_response(self):
        """
        Returns a dict of {parent case type: [subcase properties]}
        """
        result = {}
        parent_child_types = self.get_parent_child_types()
        all_case_properties = self.search_case_property_response

        for parent_type in parent_child_types:
            result[parent_type] = []
            for subcase_type in parent_child_types[parent_type]:
                result[parent_type].extend(all_case_properties[subcase_type])
        return self.clean_dict_list(result)

    @property
    def search_forms_response(self):
        forms = []
        for app in self.apps:
            for module in app.get_modules():
                for form in module.get_forms():
                    forms.append({
                        'text': form.full_path_name,
                        'id': form.unique_id,
                    })
        if not self.search_term:
            return forms
        final_forms = []
        search_terms = self.search_term.split(" ")
        for form in forms:
            matches = [t for t in search_terms if t in form['text']]
            if len(matches) == len(search_terms):
                final_forms.append(form)
        return final_forms

    def _filter_by_term(self, filter_list):
        return [f for f in filter_list if self.search_term in f]

    def _format_response(self, resp_list):
        return [{'text': r, 'id': r} for r in resp_list]

    @method_decorator(reminders_framework_permission)
    def dispatch(self, request, *args, **kwargs):
        return super(CreateScheduledReminderView, self).dispatch(request, *args, **kwargs)

    def post(self, *args, **kwargs):
        if self.action in [
            'search_case_type',
            'search_case_property',
            'search_subcase_property',
            'search_forms',
            'search_form_by_id',
        ]:
            return HttpResponse(json.dumps(getattr(self, '%s_response' % self.action)))
        if self.schedule_form.is_valid():
            self.process_schedule_form()
            return HttpResponseRedirect(reverse(RemindersListView.urlname, args=[self.domain]))
        else:
            messages.error(self.request, "There were errors saving your reminder.")
        return self.get(*args, **kwargs)

    def process_schedule_form(self):
        new_handler = CaseReminderHandler()
        self.schedule_form.save(new_handler)


class CreateComplexScheduledReminderView(CreateScheduledReminderView):
    urlname = 'create_complex_reminder_schedule'
    page_title = ugettext_noop("Schedule Multi Event Reminder")
    ui_type = UI_COMPLEX


class EditScheduledReminderView(CreateScheduledReminderView):
    urlname = 'edit_reminder_schedule'
    page_title = ugettext_noop("Edit Scheduled Reminder")

    @property
    def handler_id(self):
        return self.kwargs.get('handler_id')

    @property
    def page_name(self):
        if self.ui_type == UI_COMPLEX:
            return _("Edit Scheduled Multi Event Reminder")
        return self.page_title

    @property
    def available_languages(self):
        """
        When editing a reminder, add in any languages that are used by the
        reminder but that are not in the result from
        CreateScheduledReminderView's available_languages property.

        This is needed to be backwards-compatible with reminders created
        with the old ui that would let you specify any language, regardless
        of whether it was in the domain's list of languages or not.
        """
        result = super(EditScheduledReminderView, self).available_languages
        handler = self.reminder_handler
        for event in handler.events:
            if event.message:
                for (lang, text) in event.message.items():
                    if lang not in result:
                        result.append(lang)
        return result

    @property
    @memoized
    def schedule_form(self):
        initial = self.reminder_form_class.compute_initial(
            self.reminder_handler, self.available_languages,
        )
        if self.request.method == 'POST':
            return self.reminder_form_class(
                self.request.POST,
                initial=initial,
                is_previewer=self.is_previewer,
                domain=self.domain,
                is_edit=True,
                can_use_survey=can_use_survey_reminders(self.request),
                use_custom_content_handler=self.reminder_handler.custom_content_handler is not None,
                custom_content_handler=self.reminder_handler.custom_content_handler,
                available_languages=self.available_languages,
            )
        return self.reminder_form_class(
            initial=initial,
            is_previewer=self.is_previewer,
            domain=self.domain,
            is_edit=True,
            can_use_survey=can_use_survey_reminders(self.request),
            use_custom_content_handler=self.reminder_handler.custom_content_handler is not None,
            custom_content_handler=self.reminder_handler.custom_content_handler,
            available_languages=self.available_languages,
        )

    @property
    @memoized
    def reminder_handler(self):
        try:
            handler = CaseReminderHandler.get(self.handler_id)
            assert handler.domain == self.domain
            assert handler.doc_type == "CaseReminderHandler"
            return handler
        except (ResourceNotFound, AssertionError):
            raise Http404()

    @property
    def ui_type(self):
        return self.reminder_handler.ui_type

    @property
    def page_context(self):
        page_context = super(EditScheduledReminderView, self).page_context
        page_context.update({
            'handler_id': self.handler_id,
        })
        return page_context

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.handler_id])

    def process_schedule_form(self):
        self.schedule_form.save(self.reminder_handler)

    def rule_in_progress(self):
        messages.error(self.request, _("Please wait until the rule finishes "
            "processing before making further changes."))
        return HttpResponseRedirect(reverse(RemindersListView.urlname, args=[self.domain]))

    def get(self, *args, **kwargs):
        if self.reminder_handler.locked:
            return self.rule_in_progress()
        else:
            return super(EditScheduledReminderView, self).get(*args, **kwargs)

    def post(self, *args, **kwargs):
        if self.reminder_handler.locked:
            return self.rule_in_progress()
        else:
            return super(EditScheduledReminderView, self).post(*args, **kwargs)


class AddStructuredKeywordView(BaseMessagingSectionView):
    urlname = 'add_structured_keyword'
    page_title = ugettext_noop("New Structured Keyword")
    template_name = 'reminders/keyword.html'
    process_structured_message = True

    @property
    def parent_pages(self):
        return [
            {
                'title': KeywordsListView.page_title,
                'url': reverse(KeywordsListView.urlname, args=[self.domain]),
            },
        ]

    @property
    @memoized
    def keyword(self):
        return SurveyKeyword(domain=self.domain)

    @property
    def keyword_form(self):
        raise NotImplementedError("you must implement keyword_form")

    @property
    def page_context(self):
        def _fmt_choices(val, text):
            return {'value': val, 'text': text}
        return {
            'form': self.keyword_form,
            'form_list': get_form_list(self.domain),
        }

    @property
    @memoized
    def keyword_form(self):
        if self.request.method == 'POST':
            return KeywordForm(
                self.request.POST, domain=self.domain,
                process_structured=self.process_structured_message,
            )
        return KeywordForm(
            domain=self.domain,
            process_structured=self.process_structured_message,
        )

    def post(self, request, *args, **kwargs):
        if self.keyword_form.is_valid():
            self.keyword.keyword = self.keyword_form.cleaned_data['keyword']
            self.keyword.description = self.keyword_form.cleaned_data['description']
            self.keyword.delimiter = self.keyword_form.cleaned_data['delimiter']
            self.keyword.override_open_sessions = self.keyword_form.cleaned_data['override_open_sessions']

            self.keyword.initiator_doc_type_filter = []
            if self.keyword_form.cleaned_data['allow_keyword_use_by'] == 'users':
                self.keyword.initiator_doc_type_filter.append('CommCareUser')
            if self.keyword_form.cleaned_data['allow_keyword_use_by'] == 'cases':
                self.keyword.initiator_doc_type_filter.append('CommCareCase')

            self.keyword.actions = []
            if self.keyword_form.cleaned_data['sender_content_type'] != NO_RESPONSE:
                self.keyword.actions.append(
                    SurveyKeywordAction(
                        recipient=RECIPIENT_SENDER,
                        action=self.keyword_form.cleaned_data['sender_content_type'],
                        message_content=self.keyword_form.cleaned_data['sender_message'],
                        form_unique_id=self.keyword_form.cleaned_data['sender_form_unique_id'],
                    )
                )
            if self.process_structured_message:
                self.keyword.actions.append(
                    SurveyKeywordAction(
                        recipient=RECIPIENT_SENDER,
                        action=METHOD_STRUCTURED_SMS,
                        form_unique_id=self.keyword_form.cleaned_data['structured_sms_form_unique_id'],
                        use_named_args=self.keyword_form.cleaned_data['use_named_args'],
                        named_args=self.keyword_form.cleaned_data['named_args'],
                        named_args_separator=self.keyword_form.cleaned_data['named_args_separator'],
                    )
                )
            if self.keyword_form.cleaned_data['other_recipient_content_type'] != NO_RESPONSE:
                self.keyword.actions.append(
                    SurveyKeywordAction(
                        recipient=self.keyword_form.cleaned_data['other_recipient_type'],
                        recipient_id=self.keyword_form.cleaned_data['other_recipient_id'],
                        action=self.keyword_form.cleaned_data['other_recipient_content_type'],
                        message_content=self.keyword_form.cleaned_data['other_recipient_message'],
                        form_unique_id=self.keyword_form.cleaned_data['other_recipient_form_unique_id'],
                    )
                )

            self.keyword.save()
            return HttpResponseRedirect(reverse(KeywordsListView.urlname, args=[self.domain]))
        return self.get(request, *args, **kwargs)


class AddNormalKeywordView(AddStructuredKeywordView):
    urlname = 'add_normal_keyword'
    page_title = ugettext_noop("New Keyword")
    process_structured_message = False


class EditStructuredKeywordView(AddStructuredKeywordView):
    urlname = 'edit_structured_keyword'
    page_title = ugettext_noop("Edit Structured Keyword")

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.keyword_id])

    @property
    def keyword_id(self):
        return self.kwargs.get('keyword_id')

    @property
    @memoized
    def keyword(self):
        if self.keyword_id is None:
            raise Http404()
        sk = SurveyKeyword.get(self.keyword_id)
        if sk.domain != self.domain:
            raise Http404()
        return sk

    @property
    @memoized
    def keyword_form(self):
        initial = self.get_initial_values()
        if self.request.method == 'POST':
            form = KeywordForm(
                self.request.POST, domain=self.domain, initial=initial,
                process_structured=self.process_structured_message,
            )
            form._sk_id = self.keyword_id
            return form
        return KeywordForm(
            domain=self.domain, initial=initial,
            process_structured=self.process_structured_message,
        )

    def get_initial_values(self):
        initial = {
            'keyword': self.keyword.keyword,
            'description': self.keyword.description,
            'delimiter': self.keyword.delimiter,
            'override_open_sessions': self.keyword.override_open_sessions,
            'sender_content_type': NO_RESPONSE,
        }
        is_case_filter = "CommCareCase" in self.keyword.initiator_doc_type_filter
        is_user_filter = "CommCareUser" in self.keyword.initiator_doc_type_filter
        if is_case_filter and not is_user_filter:
            initial.update({
                'allow_keyword_use_by': 'cases',
            })
        elif is_user_filter and not is_case_filter:
            initial.update({
                'allow_keyword_use_by': 'users',
            })
        for action in self.keyword.actions:
            if action.action == METHOD_STRUCTURED_SMS:
                if self.process_structured_message:
                    initial.update({
                        'structured_sms_form_unique_id': action.form_unique_id,
                        'use_custom_delimiter': self.keyword.delimiter is not None,
                        'use_named_args_separator': action.named_args_separator is not None,
                        'use_named_args': action.use_named_args,
                        'named_args_separator': action.named_args_separator,
                        'named_args': [{"name" : k, "xpath" : v} for k, v in action.named_args.items()],
                    })
            elif action.recipient == RECIPIENT_SENDER:
                initial.update({
                    'sender_content_type': action.action,
                    'sender_message': action.message_content,
                    'sender_form_unique_id': action.form_unique_id,
                })
            else:
                initial.update({
                    'other_recipient_type': action.recipient,
                    'other_recipient_id': action.recipient_id,
                    'other_recipient_content_type': action.action,
                    'other_recipient_message': action.message_content,
                    'other_recipient_form_unique_id': action.form_unique_id,
                })
        return initial


class EditNormalKeywordView(EditStructuredKeywordView):
    urlname = 'edit_normal_keyword'
    page_title = ugettext_noop("Edit Normal Keyword")
    process_structured_message = False

    @property
    @memoized
    def keyword(self):
        sk = super(EditNormalKeywordView, self).keyword
        # don't allow structured keywords to be edited in this view.
        if METHOD_STRUCTURED_SMS in [a.action for a in sk.actions]:
            raise Http404()
        return sk


@survey_reminders_permission
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
            
            sample_data = {}
            for sample in samples:
                sample_data[sample["sample_id"]] = sample
            
            if send_followup:
                timeout_intervals = [int(followup["interval"]) * 1440 for followup in followups]
            else:
                timeout_intervals = []
            
            timeout_duration = sum(timeout_intervals) / 1440
            final_timeout = lambda wave : [((wave.end_date - wave.date).days - timeout_duration) * 1440]
            
            if survey is None:
                wave_list = []
                for wave in waves:
                    wave_list.append(SurveyWave(
                        date=parse(wave["date"]).date(),
                        time=parse(wave["time"]).time(),
                        end_date=parse(wave["end_date"]).date(),
                        form_id=wave["form_id"],
                        reminder_definitions={},
                        delegation_tasks={},
                    ))
                
                if send_automatically:
                    for wave in wave_list:
                        for sample in samples:
                            if sample["method"] == "SMS":
                                handler = CaseReminderHandler(
                                    domain = domain,
                                    nickname = "Survey '%s'" % name,
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
                                        callback_timeout_intervals = timeout_intervals + final_timeout(wave),
                                    )],
                                    schedule_length = 1,
                                    event_interpretation = EVENT_AS_SCHEDULE,
                                    max_iteration_count = 1,
                                    sample_id = sample["sample_id"],
                                    survey_incentive = sample["incentive"],
                                    submit_partial_forms = True,
                                    reminder_type=REMINDER_TYPE_SURVEY_MANAGEMENT,
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
                            wave.end_date = parse(wave_json["end_date"]).date()
                            survey.waves.append(wave)
                            unchanged_wave_json.append(wave_json)
                            continue
                
                for wave in survey.waves:
                    current_waves.remove(wave)
                
                for wave_json in unchanged_wave_json:
                    waves.remove(wave_json)
                
                # Retire reminder definitions / close delegation tasks for old waves
                for wave in current_waves:
                    for sample_id, handler_id in wave.reminder_definitions.items():
                        handler = CaseReminderHandler.get(handler_id)
                        handler.retire()
                    for sample_id, delegation_data in wave.delegation_tasks.items():
                        for case_id, delegation_case_id in delegation_data.items():
                            close_task(domain, delegation_case_id, request.couch_user.get_id)
                
                # Add in new waves
                for wave_json in waves:
                    survey.waves.append(SurveyWave(
                        date=parse(wave_json["date"]).date(),
                        time=parse(wave_json["time"]).time(),
                        end_date=parse(wave_json["end_date"]).date(),
                        form_id=wave_json["form_id"],
                        reminder_definitions={},
                        delegation_tasks={},
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
                        handler.events[0].callback_timeout_intervals = timeout_intervals + final_timeout(wave)
                        handler.nickname = "Survey '%s'" % name
                        handler.survey_incentive = sample_data[sample_id]["incentive"]
                        handler.save()
                
                # Create additional reminder definitions as necessary
                for wave in survey.waves:
                    for sample_id in new_sample_ids:
                        if sample_id not in wave.reminder_definitions:
                            handler = CaseReminderHandler(
                                domain = domain,
                                nickname = "Survey '%s'" % name,
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
                                    callback_timeout_intervals = timeout_intervals + final_timeout(wave),
                                )],
                                schedule_length = 1,
                                event_interpretation = EVENT_AS_SCHEDULE,
                                max_iteration_count = 1,
                                sample_id = sample_id,
                                survey_incentive = sample_data[sample_id]["incentive"],
                                submit_partial_forms = True,
                                reminder_type=REMINDER_TYPE_SURVEY_MANAGEMENT,
                            )
                            handler.save()
                            wave.reminder_definitions[sample_id] = handler._id
                
                # Set the rest of the survey info
                survey.name = name
                survey.followups = followups
                survey.samples = samples
                survey.send_automatically = send_automatically
                survey.send_followup = send_followup
            
            # Sort the questionnaire waves by date and time
            survey.waves = sorted(survey.waves, key = lambda wave : datetime.combine(wave.date, wave.time))
            
            # Create / Close delegation tasks as necessary for samples with method "CATI"
            survey.update_delegation_tasks(request.couch_user.get_id)
            
            survey.save()
            return HttpResponseRedirect(reverse("survey_list", args=[domain]))
    else:
        initial = {}
        if survey is not None:
            waves = []
            samples = [CommCareCaseGroup.get(sample["sample_id"]) for sample in survey.samples]
            utcnow = datetime.utcnow()
            for wave in survey.waves:
                wave_json = {
                    "date" : str(wave.date),
                    "form_id" : wave.form_id,
                    "time" : str(wave.time),
                    "ignore" : wave.has_started(survey),
                    "end_date" : str(wave.end_date),
                }
                
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
        "started" : survey.has_started() if survey is not None else False,
    }
    return render(request, "reminders/partial/add_survey.html", context)


@survey_reminders_permission
def survey_list(request, domain):
    context = {
        "domain" : domain,
        "surveys" : Survey.get_all(domain)
    }
    return render(request, "reminders/partial/survey_list.html", context)


@survey_reminders_permission
def add_sample(request, domain, sample_id=None):
    sample = None
    if sample_id is not None:
        try:
            sample = CommCareCaseGroup.get(sample_id)
        except ResourceNotFound:
            raise Http404
    
    if request.method == "POST":
        form = SurveySampleForm(request.POST, request.FILES)
        if form.is_valid():
            name            = form.cleaned_data.get("name")
            sample_contacts = form.cleaned_data.get("sample_contacts")
            time_zone       = form.cleaned_data.get("time_zone")
            use_contact_upload_file = form.cleaned_data.get("use_contact_upload_file")
            contact_upload_file = form.cleaned_data.get("contact_upload_file")
            
            if sample is None:
                sample = CommCareCaseGroup(
                    domain=domain,
                    name=name,
                    timezone=time_zone.zone
                )
            else:
                sample.name = name
                sample.timezone = time_zone.zone
            
            errors = []
            
            phone_numbers = []
            if use_contact_upload_file == "Y":
                for contact in contact_upload_file:
                    phone_numbers.append(contact["phone_number"])
            else:
                for contact in sample_contacts:
                    phone_numbers.append(contact["phone_number"])
            
            existing_number_entries = VerifiedNumber.view('sms/verified_number_by_number',
                                            keys=phone_numbers,
                                            include_docs=True
                                       ).all()
            
            for entry in existing_number_entries:
                if entry.domain != domain or entry.owner_doc_type != "CommCareCase":
                    errors.append("Cannot use phone number %s" % entry.phone_number)
            
            if len(errors) > 0:
                if use_contact_upload_file == "Y":
                    form._errors["contact_upload_file"] = form.error_class(errors)
                else:
                    form._errors["sample_contacts"] = form.error_class(errors)
            else:
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
                
                sample.cases = ([v.owner_id for v in existing_number_entries]
                                + [v.owner_id for v in newly_registered_entries])
                
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
            initial["time_zone"] = sample.timezone
            contact_info = []
            for case_id in sample.cases:
                case = CommCareCase.get(case_id)
                contact_info.append({"id":case.name, "phone_number":case.contact_phone_number, "case_id" : case_id})
            initial["sample_contacts"] = contact_info
        form = SurveySampleForm(initial=initial)
    
    context = {
        "domain" : domain,
        "form" : form,
        "sample_id" : sample_id
    }
    return render(request, "reminders/partial/add_sample.html", context)


@survey_reminders_permission
def sample_list(request, domain):
    context = {
        "domain" : domain,
        "samples": get_case_groups_in_domain(domain)
    }
    return render(request, "reminders/partial/sample_list.html", context)


@reminders_framework_permission
def edit_contact(request, domain, sample_id, case_id):
    case = CommCareCase.get(case_id)
    if case.domain != domain:
        raise Http404
    if request.method == "POST":
        form = EditContactForm(request.POST)
        if form.is_valid():
            phone_number = form.cleaned_data.get("phone_number")
            vn = VerifiedNumber.view('sms/verified_number_by_number',
                                        key=phone_number,
                                        include_docs=True,
                                    ).one()
            if vn is not None and vn.owner_id != case_id:
                form._errors["phone_number"] = form.error_class(["Phone number is already in use."])
            else:
                update_contact(domain, case_id, request.couch_user.get_id, contact_phone_number=phone_number)
                return HttpResponseRedirect(reverse("edit_sample", args=[domain, sample_id]))
    else:
        initial = {
            "phone_number" : case.get_case_property("contact_phone_number"),
        }
        form = EditContactForm(initial=initial)
    
    context = {
        "domain" : domain,
        "case" : case,
        "form" : form,
    }
    return render(request, "reminders/partial/edit_contact.html", context)


@reminders_framework_permission
def reminders_in_error(request, domain):
    handler_map = {}
    if request.method == "POST":
        form = RemindersInErrorForm(request.POST)
        if form.is_valid():
            kwargs = {}
            if is_bigcouch():
                # Force a write to all nodes before returning
                kwargs["w"] = bigcouch_quorum_count()
            current_timestamp = datetime.utcnow()
            for reminder_id in form.cleaned_data.get("selected_reminders"):
                reminder = CaseReminder.get(reminder_id)
                if reminder.domain != domain:
                    continue
                if reminder.handler_id in handler_map:
                    handler = handler_map[reminder.handler_id]
                else:
                    handler = reminder.handler
                    handler_map[reminder.handler_id] = handler
                reminder.error = False
                reminder.error_msg = None
                handler.set_next_fire(reminder, current_timestamp)
                reminder.save(**kwargs)
    
    timezone = get_timezone_for_user(request.couch_user, domain)
    reminders = []
    for reminder in CaseReminder.view("reminders/reminders_in_error", startkey=[domain], endkey=[domain, {}], include_docs=True).all():
        if reminder.handler_id in handler_map:
            handler = handler_map[reminder.handler_id]
        else:
            handler = reminder.handler
            handler_map[reminder.handler_id] = handler
        recipient = reminder.recipient
        case = reminder.case
        reminders.append({
            "reminder_id" : reminder._id,
            "handler_type" : handler.reminder_type,
            "handler_id" : reminder.handler_id,
            "handler_name" : handler.nickname,
            "case_id" : case.get_id if case is not None else None,
            "case_name" : case.name if case is not None else None,
            "next_fire" : ServerTime(reminder.next_fire).user_time(timezone).ui_string(SERVER_DATETIME_FORMAT),
            "error_msg" : reminder.error_msg or "-",
            "recipient_name" : get_recipient_name(recipient),
        })
    context = {
        "domain" : domain,
        "reminders" : reminders,
        "timezone" : timezone,
        "timezone_now" : datetime.now(tz=timezone),
    }
    return render(request, "reminders/partial/reminders_in_error.html", context)


class RemindersListView(BaseMessagingSectionView):
    template_name = 'reminders/reminders_list.html'
    urlname = "list_reminders_new"
    page_title = ugettext_noop("Reminder Definitions")

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    @property
    def can_use_survey(self):
        return can_use_survey_reminders(self.request)

    @property
    def reminders(self):
        all_handlers = CaseReminderHandler.get_handlers(self.domain,
            reminder_type_filter=REMINDER_TYPE_DEFAULT)
        if not self.can_use_survey:
            all_handlers = filter(
                lambda x: x.method not in [METHOD_IVR_SURVEY, METHOD_SMS_SURVEY],
                all_handlers
            )
        for handler in all_handlers:
            yield self._fmt_reminder_data(handler)

    @property
    def page_context(self):
        return {
            'reminders': list(self.reminders),
        }

    @property
    def reminder_id(self):
        return self.request.POST['reminderId']

    @property
    @memoized
    def reminder(self):
        return CaseReminderHandler.get(self.reminder_id)

    def _fmt_reminder_data(self, reminder):
        return {
            'id': reminder._id,
            'isActive': reminder.active,
            'caseType': reminder.case_type,
            'name': reminder.nickname,
            'url': reverse(EditScheduledReminderView.urlname, args=[self.domain, reminder._id]),
        }

    def get_action_response(self, action):
        try:
            assert self.reminder.domain == self.domain
            assert self.reminder.doc_type == "CaseReminderHandler"
            if self.reminder.locked:
                return {
                    'success': False,
                    'locked': True,
                }

            if action in [ACTION_ACTIVATE, ACTION_DEACTIVATE]:
                self.reminder.active = (action == ACTION_ACTIVATE)
                self.reminder.save()
            elif action == ACTION_DELETE:
                self.reminder.retire()
            return {
                'success': True,
            }
        except Exception as e:
            msg = ("Couldn't process action '%s' for reminder definition"
                % action)
            notify_exception(None, message=msg, details={
                'domain': self.domain,
                'handler_id': self.reminder_id,
            })
            return {
                'success': False,
            }

    def post(self, *args, **kwargs):
        action = self.request.POST.get('action')
        if action in [ACTION_ACTIVATE, ACTION_DEACTIVATE, ACTION_DELETE]:
            return HttpResponse(json.dumps(self.get_action_response(action)))
        return HttpResponse(status=400)


class KeywordsListView(BaseMessagingSectionView, CRUDPaginatedViewMixin):
    template_name = 'reminders/keyword_list.html'
    urlname = 'keyword_list'
    page_title = ugettext_noop("Keywords")

    limit_text = ugettext_noop("keywords per page")
    empty_notification = ugettext_noop("You have no keywords. Please add one!")
    loading_message = ugettext_noop("Loading keywords...")

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    @property
    def parameters(self):
        return self.request.POST if self.request.method == 'POST' else self.request.GET

    @property
    @memoized
    def total(self):
        data = SurveyKeyword.get_db().view(
            'reminders/survey_keywords',
            reduce=True,
            startkey=[self.domain],
            endkey=[self.domain, {}],
        ).first()
        return data['value'] if data else 0

    @property
    def column_names(self):
        return [
            _("Keyword"),
            _("Description"),
            _("Action"),
        ]

    @property
    def page_context(self):
        return self.pagination_context

    @property
    def paginated_list(self):
        for keyword in SurveyKeyword.get_by_domain(
            self.domain,
            limit=self.limit,
            skip=self.skip,
        ):
            yield {
                'itemData': self._fmt_keyword_data(keyword),
                'template': 'keyword-row-template',
            }

    def _fmt_keyword_data(self, keyword):
        return {
            'id': keyword._id,
            'keyword': keyword.keyword,
            'description': keyword.description,
            'editUrl': reverse(
                EditStructuredKeywordView.urlname,
                args=[self.domain, keyword._id]
            ) if keyword.is_structured_sms() else reverse(
                EditNormalKeywordView.urlname,
                args=[self.domain, keyword._id]
            ),
            'deleteModalId': 'delete-%s' % keyword._id,
        }

    def get_deleted_item_data(self, item_id):
        try:
            s = SurveyKeyword.get(item_id)
        except ResourceNotFound:
            raise Http404()
        if s.domain != self.domain or s.doc_type != "SurveyKeyword":
            raise Http404()
        s.retire()
        return {
            'itemData': self._fmt_keyword_data(s),
            'template': 'keyword-deleted-template',
        }

    def post(self, *args, **kwargs):
        return self.paginate_crud_response


def int_or_none(i):
    try:
        i = int(i)
    except (ValueError, TypeError):
        i = None
    return i


@reminders_framework_permission
def rule_progress(request, domain):
    client = get_redis_client()
    handlers = CaseReminderHandler.get_handlers(domain,
        reminder_type_filter=REMINDER_TYPE_DEFAULT)

    response = {}
    for handler in handlers:
        info = {}
        if handler.locked:
            info['complete'] = False
            current = None
            total = None

            try:
                current = client.get('reminder-rule-processing-current-%s' % handler._id)
                total = client.get('reminder-rule-processing-total-%s' % handler._id)
            except:
                continue

            info['current'] = int_or_none(current)
            info['total'] = int_or_none(total)
        else:
            info['complete'] = True

        response[handler._id] = info

    return HttpResponse(json.dumps(response))
