from __future__ import absolute_import
import json
import re
from corehq.apps.data_interfaces.forms import CaseRuleCriteriaForm, validate_case_property_name
from corehq.apps.data_interfaces.models import CreateScheduleInstanceActionDefinition
from corehq.apps.groups.models import Group
from corehq.apps.hqwebapp import crispy as hqcrispy
from crispy_forms import layout as crispy
from crispy_forms import bootstrap as twbscrispy
from crispy_forms.helper import FormHelper
from dateutil import parser
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.forms.fields import (
    BooleanField,
    CharField,
    ChoiceField,
    MultipleChoiceField,
    IntegerField,
)
from django.forms.forms import Form
from django.forms.widgets import CheckboxSelectMultiple, HiddenInput
from django.utils.functional import cached_property
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.django.fields import TrimmedCharField
from django.utils.translation import ugettext as _, ugettext_lazy
from corehq.apps.app_manager.dbaccessors import get_latest_released_app
from corehq.apps.app_manager.exceptions import FormNotFoundException
from corehq.apps.app_manager.models import Form as CCHQForm, AdvancedForm
from corehq.apps.casegroups.models import CommCareCaseGroup
from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reminders.util import get_form_list
from corehq.apps.sms.util import get_or_create_translation_doc
from corehq.apps.smsforms.models import SQLXFormsSession
from corehq.apps.users.models import CommCareUser
from corehq.messaging.scheduling.const import (
    VISIT_WINDOW_START,
    VISIT_WINDOW_END,
    VISIT_WINDOW_DUE_DATE,
)
from corehq.messaging.scheduling.exceptions import ImmediateMessageEditAttempt, UnsupportedScheduleError
from corehq.messaging.scheduling.models import (
    Schedule,
    AlertSchedule,
    TimedSchedule,
    TimedEvent,
    RandomTimedEvent,
    CasePropertyTimedEvent,
    ImmediateBroadcast,
    ScheduledBroadcast,
    SMSContent,
    EmailContent,
    SMSSurveyContent,
    CustomContent,
)
from corehq.messaging.scheduling.scheduling_partitioned.models import ScheduleInstance, CaseScheduleInstanceMixin
from couchdbkit.resource import ResourceNotFound
from langcodes import get_name as get_language_name
import six
from six.moves import range


def validate_time(value):
    error = ValidationError(_("Please enter a valid 24-hour time in the format HH:MM"))

    if not isinstance(value, (six.text_type, str)) or not re.match('^\d?\d:\d\d$', value):
        raise error

    try:
        value = parser.parse(value)
    except ValueError:
        raise error

    return value.time()


def validate_date(value):
    error = ValidationError(_("Please enter a valid date in the format YYYY-MM-DD"))

    if not isinstance(value, (six.text_type, str)) or not re.match('^\d\d\d\d-\d\d-\d\d$', value):
        raise error

    try:
        value = parser.parse(value)
    except ValueError:
        raise error

    return value.date()


class RecipientField(CharField):
    def to_python(self, value):
        if not value:
            return []
        return value.split(',')


class ScheduleForm(Form):
    # Prefix to avoid name collisions; this means all input
    # names in the HTML are prefixed with "schedule-"
    prefix = "schedule"

    SEND_DAILY = 'daily'
    SEND_WEEKLY = 'weekly'
    SEND_MONTHLY = 'monthly'
    SEND_IMMEDIATELY = 'immediately'

    STOP_AFTER_FIRST_OCCURRENCE = 'after_first_occurrence'
    STOP_AFTER_OCCURRENCES = 'after_occurrences'
    STOP_NEVER = 'never'

    CONTENT_SMS = 'sms'
    CONTENT_EMAIL = 'email'
    CONTENT_SMS_SURVEY = 'sms_survey'
    CONTENT_IVR_SURVEY = 'ivr_survey'
    CONTENT_CUSTOM_SMS = 'custom_sms'

    LANGUAGE_PROJECT_DEFAULT = 'PROJECT_DEFAULT'

    active = ChoiceField(
        required=True,
        label='',
        choices=(
            ('Y', ugettext_lazy("Active")),
            ('N', ugettext_lazy("Inactive")),
        ),
    )
    send_frequency = ChoiceField(
        required=True,
        label=ugettext_lazy('Send'),
        choices=(
            (SEND_IMMEDIATELY, ugettext_lazy('Immediately')),
            (SEND_DAILY, ugettext_lazy('Daily')),
            (SEND_WEEKLY, ugettext_lazy('Weekly')),
            (SEND_MONTHLY, ugettext_lazy('Monthly')),
        )
    )
    weekdays = MultipleChoiceField(
        required=False,
        label=ugettext_lazy('On'),
        choices=(
            ('6', ugettext_lazy('Sunday')),
            ('0', ugettext_lazy('Monday')),
            ('1', ugettext_lazy('Tuesday')),
            ('2', ugettext_lazy('Wednesday')),
            ('3', ugettext_lazy('Thursday')),
            ('4', ugettext_lazy('Friday')),
            ('5', ugettext_lazy('Saturday')),
        ),
        widget=CheckboxSelectMultiple()
    )
    days_of_month = MultipleChoiceField(
        required=False,
        label=ugettext_lazy('On Days'),
        choices=(
            # The actual choices are rendered by a template
            tuple((str(x), '') for x in range(-3, 0)) +
            tuple((str(x), '') for x in range(1, 29))
        )
    )
    send_time_type = ChoiceField(
        required=True,
        choices=(
            (TimedSchedule.EVENT_SPECIFIC_TIME, ugettext_lazy("A specific time")),
            (TimedSchedule.EVENT_RANDOM_TIME, ugettext_lazy("A random time")),
        )
    )
    send_time = CharField(required=False)
    window_length = IntegerField(
        required=False,
        min_value=1,
        max_value=1439,
        label='',
    )
    stop_type = ChoiceField(
        required=False,
        choices=(
            # The text for STOP_AFTER_FIRST_OCCURRENCE and STOP_AFTER_OCCURRENCES gets set dynamically
            (STOP_AFTER_FIRST_OCCURRENCE, ''),
            (STOP_AFTER_OCCURRENCES, ''),
            (STOP_NEVER, ugettext_lazy('Never')),
        )
    )
    occurrences = IntegerField(
        required=False,
        min_value=1,
        label='',
    )
    recipient_types = MultipleChoiceField(
        required=True,
        label=ugettext_lazy('Recipient(s)'),
        choices=(
            (ScheduleInstance.RECIPIENT_TYPE_MOBILE_WORKER, ugettext_lazy("Users")),
            (ScheduleInstance.RECIPIENT_TYPE_USER_GROUP, ugettext_lazy("User Groups")),
            (ScheduleInstance.RECIPIENT_TYPE_LOCATION, ugettext_lazy("User Organizations")),
            (ScheduleInstance.RECIPIENT_TYPE_CASE_GROUP, ugettext_lazy("Case Groups")),
        )
    )
    user_recipients = RecipientField(
        required=False,
        label=ugettext_lazy("User Recipient(s)"),
    )
    user_group_recipients = RecipientField(
        required=False,
        label=ugettext_lazy("User Group Recipient(s)"),
    )
    user_organization_recipients = RecipientField(
        required=False,
        label=ugettext_lazy("User Organization Recipient(s)"),
    )
    include_descendant_locations = BooleanField(
        required=False,
        label=ugettext_lazy("Also send to users at child locations"),
    )
    case_group_recipients = RecipientField(
        required=False,
        label=ugettext_lazy("Case Group Recipient(s)"),
    )
    content = ChoiceField(
        required=True,
        label=ugettext_lazy("What to send"),
        choices=(
            (CONTENT_SMS, ugettext_lazy('SMS')),
            (CONTENT_EMAIL, ugettext_lazy('Email')),
        )
    )
    subject = CharField(
        required=False,
        widget=HiddenInput,
    )
    message = CharField(
        required=False,
        widget=HiddenInput,
    )
    form_unique_id = ChoiceField(
        required=False,
        label=ugettext_lazy("Form"),
    )
    survey_expiration_in_hours = IntegerField(
        required=False,
        min_value=1,
        max_value=SQLXFormsSession.MAX_SESSION_LENGTH // 60,
        label='',
    )
    default_language_code = ChoiceField(
        required=True,
        label=ugettext_lazy("Default Language"),
    )
    survey_reminder_intervals_enabled = ChoiceField(
        required=False,
        choices=(
            ('N', ugettext_lazy("Disabled")),
            ('Y', ugettext_lazy("Enabled")),
        ),
    )
    survey_reminder_intervals = CharField(
        required=False,
        label='',
    )
    submit_partially_completed_forms = BooleanField(
        required=False,
        label=ugettext_lazy("When the survey session expires, submit a partially "
                            "completed form if the survey is not completed"),
    )
    include_case_updates_in_partial_submissions = BooleanField(
        required=False,
        label=ugettext_lazy("Include case updates in partially completed submissions"),
    )

    def update_send_frequency_choices(self, initial_value):
        def filter_function(two_tuple):
            if initial_value == self.SEND_IMMEDIATELY:
                return two_tuple[0] == self.SEND_IMMEDIATELY
            else:
                return two_tuple[0] != self.SEND_IMMEDIATELY

        self.fields['send_frequency'].choices = [
            c for c in self.fields['send_frequency'].choices if filter_function(c)
        ]

    def set_default_language_code_choices(self):
        choices = [
            (self.LANGUAGE_PROJECT_DEFAULT, _("Project Default")),
        ]

        choices.extend([
            (language_code, _(get_language_name(language_code)))
            for language_code in self.language_list
        ])

        self.fields['default_language_code'].choices = choices

    def add_intial_for_immediate_schedule(self, initial):
        initial['send_frequency'] = self.SEND_IMMEDIATELY

    def add_intial_for_daily_schedule(self, initial):
        initial['send_frequency'] = self.SEND_DAILY

    def add_intial_for_weekly_schedule(self, initial):
        weekdays = [(self.initial_schedule.start_day_of_week + e.day) % 7
                    for e in self.initial_schedule.memoized_events]
        initial['send_frequency'] = self.SEND_WEEKLY
        initial['weekdays'] = [str(day) for day in weekdays]

    def add_intial_for_monthly_schedule(self, initial):
        initial['send_frequency'] = self.SEND_MONTHLY
        initial['days_of_month'] = [str(e.day) for e in self.initial_schedule.memoized_events]

    def add_initial_for_send_time(self, initial):
        if self.initial_schedule.event_type == TimedSchedule.EVENT_SPECIFIC_TIME:
            initial['send_time'] = self.initial_schedule.memoized_events[0].time.strftime('%H:%M')
        elif self.initial_schedule.event_type == TimedSchedule.EVENT_RANDOM_TIME:
            initial['send_time'] = self.initial_schedule.memoized_events[0].time.strftime('%H:%M')
            initial['window_length'] = self.initial_schedule.memoized_events[0].window_length
        else:
            raise ValueError("Unexpected event_type: %s" % self.initial_schedule.event_type)

    def add_initial_for_timed_schedule(self, initial):
        initial['send_time_type'] = self.initial_schedule.event_type

        self.add_initial_for_send_time(initial)

        if self.initial_schedule.total_iterations == TimedSchedule.REPEAT_INDEFINITELY:
            initial['stop_type'] = self.STOP_NEVER
        elif self.initial_schedule.total_iterations == 1:
            initial['stop_type'] = self.STOP_AFTER_FIRST_OCCURRENCE
        else:
            initial['stop_type'] = self.STOP_AFTER_OCCURRENCES
            initial['occurrences'] = self.initial_schedule.total_iterations

    def add_initial_recipients(self, recipients, initial):
        recipient_types = set()
        user_recipients = []
        user_group_recipients = []
        user_organization_recipients = []
        case_group_recipients = []

        for recipient_type, recipient_id in recipients:
            recipient_types.add(recipient_type)
            if recipient_type == ScheduleInstance.RECIPIENT_TYPE_MOBILE_WORKER:
                user_recipients.append(recipient_id)
            elif recipient_type == ScheduleInstance.RECIPIENT_TYPE_USER_GROUP:
                user_group_recipients.append(recipient_id)
            elif recipient_type == ScheduleInstance.RECIPIENT_TYPE_LOCATION:
                user_organization_recipients.append(recipient_id)
            elif recipient_type == ScheduleInstance.RECIPIENT_TYPE_CASE_GROUP:
                case_group_recipients.append(recipient_id)

        initial.update({
            'recipient_types': list(recipient_types),
            'user_recipients': ','.join(user_recipients),
            'user_group_recipients': ','.join(user_group_recipients),
            'user_organization_recipients': ','.join(user_organization_recipients),
            'case_group_recipients': ','.join(case_group_recipients),
            'include_descendant_locations': self.initial_schedule.include_descendant_locations,
        })

    def add_initial_for_content(self, result):
        content = self.initial_schedule.memoized_events[0].content
        if isinstance(content, SMSContent):
            result['content'] = self.CONTENT_SMS
            result['message'] = content.message
        elif isinstance(content, EmailContent):
            result['content'] = self.CONTENT_EMAIL
            result['subject'] = content.subject
            result['message'] = content.message
        elif isinstance(content, SMSSurveyContent):
            result['content'] = self.CONTENT_SMS_SURVEY
            result['form_unique_id'] = content.form_unique_id
            result['survey_expiration_in_hours'] = content.expire_after // 60
            result['submit_partially_completed_forms'] = content.submit_partially_completed_forms
            result['include_case_updates_in_partial_submissions'] = \
                content.include_case_updates_in_partial_submissions

            if content.reminder_intervals:
                result['survey_reminder_intervals_enabled'] = 'Y'
                result['survey_reminder_intervals'] = ', '.join([str(i) for i in content.reminder_intervals])
            else:
                result['survey_reminder_intervals_enabled'] = 'N'
        else:
            raise TypeError("Unexpected content type: %s" % type(content))

    def compute_initial(self):
        result = {}
        schedule = self.initial_schedule
        if schedule:
            result['active'] = 'Y' if schedule.active else 'N'
            result['default_language_code'] = (
                schedule.default_language_code
                if schedule.default_language_code
                else self.LANGUAGE_PROJECT_DEFAULT
            )
            if isinstance(schedule, AlertSchedule):
                if schedule.ui_type == Schedule.UI_TYPE_IMMEDIATE:
                    self.add_intial_for_immediate_schedule(result)
                else:
                    raise UnsupportedScheduleError(
                        "Unexpected Schedule ui_type '%s' for AlertSchedule '%s'" %
                        (schedule.ui_type, schedule.schedule_id)
                    )
            elif isinstance(schedule, TimedSchedule):
                if schedule.ui_type == Schedule.UI_TYPE_DAILY:
                    self.add_intial_for_daily_schedule(result)
                elif schedule.ui_type == Schedule.UI_TYPE_WEEKLY:
                    self.add_intial_for_weekly_schedule(result)
                elif schedule.ui_type == Schedule.UI_TYPE_MONTHLY:
                    self.add_intial_for_monthly_schedule(result)
                else:
                    raise UnsupportedScheduleError(
                        "Unexpected Schedule ui_type '%s' for TimedSchedule '%s'" %
                        (schedule.ui_type, schedule.schedule_id)
                    )

                self.add_initial_for_timed_schedule(result)

            self.add_initial_for_content(result)

        return result

    @memoized
    def get_form_and_app(self, form_unique_id):
        """
        Returns the form and app associated with the primary application
        document (i.e., not a build).
        """
        error_msg = _("Please choose a form")
        try:
            form, app = CCHQForm.get_form(form_unique_id, and_app=True)
        except:
            raise ValidationError(error_msg)

        if app.domain != self.domain:
            raise ValidationError(error_msg)

        return form, app

    @memoized
    def get_latest_released_form_and_app(self, form_unique_id):
        """
        Returns the form and app associated with the latest released
        build of an app.
        """
        form, app = self.get_form_and_app(form_unique_id)

        latest_released_app = get_latest_released_app(app.domain, app.get_id)
        if latest_released_app is None:
            raise ValidationError(_("Please make a released build of the application"))

        try:
            latest_released_form = latest_released_app.get_form(form_unique_id)
        except FormNotFoundException:
            raise ValidationError(_("Form not found in latest released app build"))

        return latest_released_form, latest_released_app

    def __init__(self, domain, schedule, can_use_sms_surveys, *args, **kwargs):
        self.domain = domain
        self.initial_schedule = schedule
        self.can_use_sms_surveys = can_use_sms_surveys

        if kwargs.get('initial'):
            raise ValueError("Initial values are set by the form")

        initial = {}
        if schedule:
            initial = self.compute_initial()
            kwargs['initial'] = initial

        super(ScheduleForm, self).__init__(*args, **kwargs)

        self.add_additional_content_types()
        self.set_form_unique_id_choices()
        self.set_default_language_code_choices()
        if initial.get('send_frequency'):
            self.update_send_frequency_choices(initial.get('send_frequency'))

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.form_class = 'form form-horizontal'
        self.helper.label_class = 'col-sm-2 col-md-2 col-lg-2'
        self.helper.field_class = 'col-sm-10 col-md-7 col-lg-5'

        self.helper.layout = crispy.Layout(*self.get_layout_fields())

    @cached_property
    def form_choices(self):
        return [(form['code'], form['name']) for form in get_form_list(self.domain)]

    def add_additional_content_types(self):
        if (
            self.can_use_sms_surveys or
            (self.initial_schedule and self.initial_schedule.memoized_uses_sms_survey)
        ):
            self.fields['content'].choices += [
                (self.CONTENT_SMS_SURVEY, _("SMS Survey")),
            ]

    def set_form_unique_id_choices(self):
        self.fields['form_unique_id'].choices = self.form_choices

    @property
    def scheduling_fieldset_legend(self):
        return _("Scheduling")

    def get_layout_fields(self):
        return [
            crispy.Fieldset(
                '',
                hqcrispy.B3MultiField(
                    '',
                    crispy.Div(
                        twbscrispy.InlineField('active'),
                        css_class='col-sm-3',
                    ),
                ),
            ),
            crispy.Fieldset(
                self.scheduling_fieldset_legend,
                *self.get_scheduling_layout_fields()
            ),
            crispy.Fieldset(
                _("Recipients"),
                *self.get_recipients_layout_fields()
            ),
            crispy.Fieldset(
                _("Content"),
                *self.get_content_layout_fields()
            ),
            crispy.Fieldset(
                _("Advanced Survey Options"),
                *self.get_advanced_survey_layout_fields(),
                data_bind="visible: content() === '%s'" % self.CONTENT_SMS_SURVEY
            ),
            crispy.Fieldset(
                _("Advanced"),
                *self.get_advanced_layout_fields()
            ),
        ]

    def get_start_date_layout_fields(self):
        raise NotImplementedError()

    def get_extra_timing_fields(self):
        return []

    def get_scheduling_layout_fields(self):
        result = [
            crispy.Field(
                'send_frequency',
                data_bind='value: send_frequency',
            ),
            crispy.Div(
                crispy.Field(
                    'weekdays',
                    data_bind='checked: weekdays',
                ),
                data_bind='visible: showWeekdaysInput',
            ),
            hqcrispy.B3MultiField(
                _("On Days"),
                crispy.Field(
                    'days_of_month',
                    template='scheduling/partial/days_of_month_picker.html',
                ),
                data_bind='visible: showDaysOfMonthInput',
            ),
            hqcrispy.B3MultiField(
                _("At"),
                crispy.Div(
                    twbscrispy.InlineField(
                        'send_time_type',
                        data_bind='value: send_time_type',
                    ),
                    css_class='col-sm-4',
                ),
                crispy.Div(
                    twbscrispy.InlineField(
                        'send_time',
                        template='scheduling/partial/time_picker.html',
                    ),
                    data_bind=("visible: send_time_type() === '%s' || send_time_type() === '%s'"
                               % (TimedSchedule.EVENT_SPECIFIC_TIME, TimedSchedule.EVENT_RANDOM_TIME)),
                ),
                *self.get_extra_timing_fields(),
                data_bind="visible: showTimeInput"
            ),
            hqcrispy.B3MultiField(
                _("Random Window Length (minutes)"),
                crispy.Div(
                    crispy.Field('window_length'),
                ),
                data_bind=("visible: showTimeInput() && send_time_type() === '%s'"
                           % TimedSchedule.EVENT_RANDOM_TIME),
            ),
        ]

        result.extend(self.get_start_date_layout_fields())

        result.extend([
            hqcrispy.B3MultiField(
                _("Stop"),
                crispy.Div(
                    twbscrispy.InlineField(
                        'stop_type',
                        data_bind='value: stop_type',
                    ),
                    css_class='col-sm-6',
                ),
                crispy.Div(
                    twbscrispy.InlineField(
                        'occurrences',
                        data_bind='value: occurrences',
                    ),
                    css_class='col-sm-6',
                    data_bind="visible: stop_type() === '%s'" % self.STOP_AFTER_OCCURRENCES,
                ),
                data_bind='visible: showStopInput',
            ),
            hqcrispy.B3MultiField(
                "",
                crispy.HTML(
                    '<span>%s</span> <span data-bind="text: computedEndDate"></span>'
                    % _("Date of final occurrence:"),
                ),
                data_bind="visible: computedEndDate() !== ''",
            ),
        ])

        return result

    def get_recipients_layout_fields(self):
        return [
            hqcrispy.B3MultiField(
                _("Recipient(s)"),
                crispy.Field(
                    'recipient_types',
                    template='scheduling/partial/recipient_types_picker.html',
                ),
            ),
            crispy.Div(
                crispy.Field(
                    'user_recipients',
                    data_bind='value: user_recipients.value',
                    placeholder=_("Select mobile worker(s)")
                ),
                data_bind="visible: recipientTypeSelected('%s')" % ScheduleInstance.RECIPIENT_TYPE_MOBILE_WORKER,
            ),
            crispy.Div(
                crispy.Field(
                    'user_group_recipients',
                    data_bind='value: user_group_recipients.value',
                    placeholder=_("Select user group(s)")
                ),
                data_bind="visible: recipientTypeSelected('%s')" % ScheduleInstance.RECIPIENT_TYPE_USER_GROUP,
            ),
            crispy.Div(
                crispy.Field(
                    'user_organization_recipients',
                    data_bind='value: user_organization_recipients.value',
                    placeholder=_("Select user organization(s)")
                ),
                crispy.Field('include_descendant_locations'),
                data_bind="visible: recipientTypeSelected('%s')" % ScheduleInstance.RECIPIENT_TYPE_LOCATION,
            ),
            crispy.Div(
                crispy.Field(
                    'case_group_recipients',
                    data_bind='value: case_group_recipients.value',
                    placeholder=_("Select case group(s)")
                ),
                data_bind="visible: recipientTypeSelected('%s')" % ScheduleInstance.RECIPIENT_TYPE_CASE_GROUP,
            ),
        ]

    def get_content_layout_fields(self):
        return [
            crispy.Field('content', data_bind='value: content'),
            hqcrispy.B3MultiField(
                _("Subject"),
                crispy.Field(
                    'subject',
                    data_bind='value: subject.messagesJSONString',
                ),
                crispy.Div(
                    crispy.Div(template='scheduling/partial/message_configuration.html'),
                    data_bind='with: subject',
                ),
                data_bind="visible: content() === '%s'" % self.CONTENT_EMAIL,
            ),
            hqcrispy.B3MultiField(
                _("Message"),
                crispy.Field(
                    'message',
                    data_bind='value: message.messagesJSONString',
                ),
                crispy.Div(
                    crispy.Div(template='scheduling/partial/message_configuration.html'),
                    data_bind='with: message',
                ),
                data_bind=(
                    "visible: content() === '%s' || content() === '%s'" % (self.CONTENT_SMS, self.CONTENT_EMAIL)
                ),
            ),
            crispy.Div(
                crispy.Field('form_unique_id'),
                hqcrispy.B3MultiField(
                    _("Expire After"),
                    crispy.Div(
                        twbscrispy.InlineField('survey_expiration_in_hours'),
                        css_class='col-sm-4',
                    ),
                    crispy.HTML("<span>%s</span>" % _("hour(s)")),
                ),
                hqcrispy.B3MultiField(
                    _("Reminder Intervals"),
                    crispy.Div(
                        twbscrispy.InlineField(
                            'survey_reminder_intervals_enabled',
                            data_bind='value: survey_reminder_intervals_enabled',
                        ),
                        css_class='col-sm-4',
                    ),
                    crispy.Div(
                        twbscrispy.InlineField(
                            'survey_reminder_intervals',
                            placeholder=_("e.g., 30, 60"),
                        ),
                        data_bind="visible: survey_reminder_intervals_enabled() === 'Y'",
                        css_class='col-sm-4',
                    ),
                ),
                hqcrispy.B3MultiField(
                    '',
                    crispy.HTML(
                        '<p class="help-block"><i class="fa fa-info-circle"></i> %s</p>' %
                        _("Specify a list of comma-separated intervals in minutes. At each interval, if "
                          "the survey session is still open, the system will resend the current question in the "
                          "open survey.")
                    ),
                    data_bind="visible: survey_reminder_intervals_enabled() === 'Y'",
                ),
                data_bind="visible: content() === '%s'" % self.CONTENT_SMS_SURVEY,
            ),
        ]

    def get_advanced_layout_fields(self):
        return [
            crispy.Field('default_language_code'),
        ]

    def get_advanced_survey_layout_fields(self):
        return [
            crispy.Field(
                'submit_partially_completed_forms',
                data_bind='checked: submit_partially_completed_forms',
            ),
            crispy.Div(
                crispy.Field(
                    'include_case_updates_in_partial_submissions',
                ),
                data_bind='visible: submit_partially_completed_forms()',
            )
        ]

    @cached_property
    def language_list(self):
        tdoc = get_or_create_translation_doc(self.domain)
        result = set(tdoc.langs)

        if self.initial_schedule:
            result |= self.initial_schedule.memoized_language_set

        result.discard('*')

        return list(result)

    @property
    def current_values(self):
        values = {}
        for field_name in self.fields.keys():
            values[field_name] = self[field_name].value()
        return values

    @property
    def current_select2_user_recipients(self):
        value = self['user_recipients'].value()
        if not value:
            return []

        result = []
        for user_id in value.strip().split(','):
            user_id = user_id.strip()
            user = CommCareUser.get_by_user_id(user_id, domain=self.domain)
            result.append({"id": user_id, "text": user.raw_username})

        return result

    @property
    def current_select2_user_group_recipients(self):
        value = self['user_group_recipients'].value()
        if not value:
            return []

        result = []
        for group_id in value.strip().split(','):
            group_id = group_id.strip()
            group = Group.get(group_id)
            if group.domain != self.domain:
                continue
            result.append({"id": group_id, "text": group.name})

        return result

    @property
    def current_select2_user_organization_recipients(self):
        value = self['user_organization_recipients'].value()
        if not value:
            return []

        result = []
        for location_id in value.strip().split(','):
            location_id = location_id.strip()
            try:
                location = SQLLocation.objects.get(domain=self.domain, location_id=location_id)
            except SQLLocation.DoesNotExist:
                continue

            result.append({"id": location_id, "text": location.name})

        return result

    @property
    def current_select2_case_group_recipients(self):
        value = self['case_group_recipients'].value()
        if not value:
            return []

        result = []
        for case_group_id in value.strip().split(','):
            case_group_id = case_group_id.strip()
            case_group = CommCareCaseGroup.get(case_group_id)
            if case_group.domain != self.domain:
                continue

            result.append({"id": case_group_id, "text": case_group.name})

        return result

    @property
    def current_visit_scheduler_form(self):
        """
        Only used in the ConditionalAlertScheduleForm
        """
        return {}

    @property
    def uses_sms_survey(self):
        return self.cleaned_data.get('content') == self.CONTENT_SMS_SURVEY

    def clean_active(self):
        return self.cleaned_data.get('active') == 'Y'

    def clean_user_recipients(self):
        if ScheduleInstance.RECIPIENT_TYPE_MOBILE_WORKER not in self.cleaned_data.get('recipient_types', []):
            return []

        data = self.cleaned_data['user_recipients']

        if not data:
            raise ValidationError(_("Please specify the user(s) or deselect users as recipients"))

        for user_id in data:
            user = CommCareUser.get_by_user_id(user_id, domain=self.domain)
            if not user:
                raise ValidationError(
                    _("One or more users were unexpectedly not found. Please select user(s) again.")
                )

        return data

    def clean_user_group_recipients(self):
        if ScheduleInstance.RECIPIENT_TYPE_USER_GROUP not in self.cleaned_data.get('recipient_types', []):
            return []

        data = self.cleaned_data['user_group_recipients']

        if not data:
            raise ValidationError(_("Please specify the groups(s) or deselect user groups as recipients"))

        not_found_error = ValidationError(
            _("One or more user groups were unexpectedly not found. Please select group(s) again.")
        )

        for group_id in data:
            try:
                group = Group.get(group_id)
            except ResourceNotFound:
                raise not_found_error

            if group.doc_type != 'Group':
                raise not_found_error

            if group.domain != self.domain:
                raise not_found_error

        return data

    def clean_user_organization_recipients(self):
        if ScheduleInstance.RECIPIENT_TYPE_LOCATION not in self.cleaned_data.get('recipient_types', []):
            return []

        data = self.cleaned_data['user_organization_recipients']

        if not data:
            raise ValidationError(
                _("Please specify the organization(s) or deselect user organizations as recipients")
            )

        for location_id in data:
            try:
                SQLLocation.objects.get(domain=self.domain, location_id=location_id, is_archived=False)
            except SQLLocation.DoesNotExist:
                raise ValidationError(
                    _("One or more user organizations were unexpectedly not found. "
                      "Please select organization(s) again.")
                )

        return data

    def clean_case_group_recipients(self):
        if ScheduleInstance.RECIPIENT_TYPE_CASE_GROUP not in self.cleaned_data.get('recipient_types', []):
            return []

        data = self.cleaned_data['case_group_recipients']

        if not data:
            raise ValidationError(
                _("Please specify the case groups(s) or deselect case groups as recipients")
            )

        not_found_error = ValidationError(
            _("One or more case groups were unexpectedly not found. Please select group(s) again.")
        )

        for case_group_id in data:
            try:
                case_group = CommCareCaseGroup.get(case_group_id)
            except ResourceNotFound:
                raise not_found_error

            if case_group.doc_type != 'CommCareCaseGroup':
                raise not_found_error

            if case_group.domain != self.domain:
                raise not_found_error

        return data

    def clean_weekdays(self):
        if self.cleaned_data.get('send_frequency') != self.SEND_WEEKLY:
            return None

        weeekdays = self.cleaned_data.get('weekdays')
        if not weeekdays:
            raise ValidationError(_("Please select the applicable day(s) of the week."))

        return [int(i) for i in weeekdays]

    def clean_days_of_month(self):
        if self.cleaned_data.get('send_frequency') != self.SEND_MONTHLY:
            return None

        days_of_month = self.cleaned_data.get('days_of_month')
        if not days_of_month:
            raise ValidationError(_("Please select the applicable day(s) of the month."))

        return [int(i) for i in days_of_month]

    def clean_send_time(self):
        if (
            self.cleaned_data.get('send_frequency') == self.SEND_IMMEDIATELY or
            self.cleaned_data.get('send_time_type') not in [
                TimedSchedule.EVENT_SPECIFIC_TIME, TimedSchedule.EVENT_RANDOM_TIME
            ]
        ):
            return None

        return validate_time(self.cleaned_data.get('send_time'))

    def clean_window_length(self):
        if (
            self.cleaned_data.get('send_frequency') == self.SEND_IMMEDIATELY or
            self.cleaned_data.get('send_time_type') != TimedSchedule.EVENT_RANDOM_TIME
        ):
            return None

        value = self.cleaned_data.get('window_length')
        if value is None:
            raise ValidationError(_("This field is required."))

        return value

    def clean_stop_type(self):
        if self.cleaned_data.get('send_frequency') == self.SEND_IMMEDIATELY:
            return None

        stop_type = self.cleaned_data.get('stop_type')
        if not stop_type:
            raise ValidationError(_("This field is required"))

        return stop_type

    def clean_occurrences(self):
        if (
            self.cleaned_data.get('send_frequency') == self.SEND_IMMEDIATELY or
            self.cleaned_data.get('stop_type') != self.STOP_AFTER_OCCURRENCES
        ):
            return None

        error = ValidationError(_("Please enter a whole number greater than 0"))

        occurrences = self.cleaned_data.get('occurrences')
        try:
            occurrences = int(occurrences)
        except (TypeError, ValueError):
            raise error

        if occurrences <= 0:
            raise error

        return occurrences

    def clean_subject(self):
        if self.cleaned_data.get('content') != self.CONTENT_EMAIL:
            return None

        return self._clean_message_field('subject')

    def clean_message(self):
        if self.cleaned_data.get('content') not in (self.CONTENT_SMS, self.CONTENT_EMAIL):
            return None

        return self._clean_message_field('message')

    def _clean_message_field(self, field_name):
        value = json.loads(self.cleaned_data[field_name])
        cleaned_value = {k: v.strip() for k, v in value.items()}

        if '*' in cleaned_value:
            if not cleaned_value['*']:
                raise ValidationError(_("This field is required"))
            return cleaned_value

        for expected_language_code in self.language_list:
            if not cleaned_value.get(expected_language_code):
                raise ValidationError(_("Please fill out all translations"))

        return cleaned_value

    def clean_form_unique_id(self):
        if self.cleaned_data.get('content') != self.CONTENT_SMS_SURVEY:
            return None

        value = self.cleaned_data.get('form_unique_id')
        if not value:
            raise ValidationError(_("This field is required"))

        self.get_form_and_app(value)
        return value

    def clean_survey_expiration_in_hours(self):
        if self.cleaned_data.get('content') != self.CONTENT_SMS_SURVEY:
            return None

        value = self.cleaned_data.get('survey_expiration_in_hours')
        if not value:
            raise ValidationError(_("This field is required"))

        return value

    def clean_survey_reminder_intervals(self):
        if self.cleaned_data.get('content') != self.CONTENT_SMS_SURVEY:
            return None

        if self.cleaned_data.get('survey_reminder_intervals_enabled') != 'Y':
            return []

        value = self.cleaned_data.get('survey_reminder_intervals')
        if not value:
            raise ValidationError(_("Please specify the reminder intervals or disable them"))

        intervals = []
        for interval in value.split(','):
            try:
                interval = int(interval)
            except (ValueError, TypeError):
                raise ValidationError(_("Intervals must be positive numbers"))

            if interval <= 0:
                raise ValidationError(_("Intervals must be positive numbers"))

            intervals.append(interval)

        survey_expiration_in_hours = self.cleaned_data.get('survey_expiration_in_hours')
        if survey_expiration_in_hours:
            survey_expiration_in_minutes = survey_expiration_in_hours * 60
            if sum(intervals) >= survey_expiration_in_minutes:
                raise ValidationError(
                    _("Reminder intervals must add up to less than {} based "
                      "on the current survey expiration").format(survey_expiration_in_minutes)
                )

        return intervals

    def distill_content(self):
        if self.cleaned_data['content'] == self.CONTENT_SMS:
            return SMSContent(
                message=self.cleaned_data['message']
            )
        elif self.cleaned_data['content'] == self.CONTENT_EMAIL:
            return EmailContent(
                subject=self.cleaned_data['subject'],
                message=self.cleaned_data['message'],
            )
        elif self.cleaned_data['content'] == self.CONTENT_SMS_SURVEY:
            return SMSSurveyContent(
                form_unique_id=self.cleaned_data['form_unique_id'],
                expire_after=self.cleaned_data['survey_expiration_in_hours'] * 60,
                reminder_intervals=self.cleaned_data['survey_reminder_intervals'],
                submit_partially_completed_forms=self.cleaned_data['submit_partially_completed_forms'],
                include_case_updates_in_partial_submissions=
                    self.cleaned_data['include_case_updates_in_partial_submissions']
            )
        else:
            raise ValueError("Unexpected value for content: '%s'" % self.cleaned_data['content'])

    def distill_recipients(self):
        form_data = self.cleaned_data
        return (
            [(ScheduleInstance.RECIPIENT_TYPE_MOBILE_WORKER, user_id)
             for user_id in form_data['user_recipients']] +
            [(ScheduleInstance.RECIPIENT_TYPE_USER_GROUP, group_id)
             for group_id in form_data['user_group_recipients']] +
            [(ScheduleInstance.RECIPIENT_TYPE_LOCATION, location_id)
             for location_id in form_data['user_organization_recipients']] +
            [(ScheduleInstance.RECIPIENT_TYPE_CASE_GROUP, case_group_id)
             for case_group_id in form_data['case_group_recipients']]
        )

    def distill_total_iterations(self):
        form_data = self.cleaned_data
        if form_data['stop_type'] == self.STOP_NEVER:
            return TimedSchedule.REPEAT_INDEFINITELY
        elif form_data['stop_type'] == self.STOP_AFTER_FIRST_OCCURRENCE:
            return 1

        return form_data['occurrences']

    def distill_default_language_code(self):
        value = self.cleaned_data['default_language_code']
        if value == self.LANGUAGE_PROJECT_DEFAULT:
            return None
        else:
            return value

    def distill_extra_scheduling_options(self):
        form_data = self.cleaned_data
        return {
            'active': form_data['active'],
            'default_language_code': self.distill_default_language_code(),
            'include_descendant_locations': (
                ScheduleInstance.RECIPIENT_TYPE_LOCATION in form_data['recipient_types'] and
                form_data['include_descendant_locations']
            ),
        }

    def distill_start_offset(self):
        raise NotImplementedError()

    def distill_start_day_of_week(self):
        raise NotImplementedError()

    def distill_model_timed_event(self):
        event_type = self.cleaned_data['send_time_type']
        if event_type == TimedSchedule.EVENT_SPECIFIC_TIME:
            return TimedEvent(
                time=self.cleaned_data['send_time'],
            )
        elif event_type == TimedSchedule.EVENT_RANDOM_TIME:
            return RandomTimedEvent(
                time=self.cleaned_data['send_time'],
                window_length=self.cleaned_data['window_length'],
            )
        else:
            raise ValueError("Unexpected send_time_type: %s" % event_type)

    def assert_alert_schedule(self, schedule):
        if not isinstance(schedule, AlertSchedule):
            raise TypeError("Expected AlertSchedule")

    def assert_timed_schedule(self, schedule):
        if not isinstance(schedule, TimedSchedule):
            raise TypeError("Expected TimedSchedule")

    def save_immediate_schedule(self):
        content = self.distill_content()
        extra_scheduling_options = self.distill_extra_scheduling_options()

        if self.initial_schedule:
            schedule = self.initial_schedule
            self.assert_alert_schedule(schedule)
            schedule.set_simple_alert(content, extra_options=extra_scheduling_options)
        else:
            schedule = AlertSchedule.create_simple_alert(self.domain, content,
                extra_options=extra_scheduling_options)

        return schedule

    def save_daily_schedule(self):
        form_data = self.cleaned_data
        total_iterations = self.distill_total_iterations()
        content = self.distill_content()
        extra_scheduling_options = self.distill_extra_scheduling_options()

        if self.initial_schedule:
            schedule = self.initial_schedule
            self.assert_timed_schedule(schedule)
            schedule.set_simple_daily_schedule(
                self.distill_model_timed_event(),
                content,
                total_iterations=total_iterations,
                start_offset=self.distill_start_offset(),
                extra_options=extra_scheduling_options,
            )
        else:
            schedule = TimedSchedule.create_simple_daily_schedule(
                self.domain,
                self.distill_model_timed_event(),
                content,
                total_iterations=total_iterations,
                start_offset=self.distill_start_offset(),
                extra_options=extra_scheduling_options,
            )

        return schedule

    def save_weekly_schedule(self):
        form_data = self.cleaned_data
        total_iterations = self.distill_total_iterations()
        content = self.distill_content()
        extra_scheduling_options = self.distill_extra_scheduling_options()

        if self.initial_schedule:
            schedule = self.initial_schedule
            self.assert_timed_schedule(schedule)
            schedule.set_simple_weekly_schedule(
                self.distill_model_timed_event(),
                content,
                form_data['weekdays'],
                self.distill_start_day_of_week(),
                total_iterations=total_iterations,
                extra_options=extra_scheduling_options,
            )
        else:
            schedule = TimedSchedule.create_simple_weekly_schedule(
                self.domain,
                self.distill_model_timed_event(),
                content,
                form_data['weekdays'],
                self.distill_start_day_of_week(),
                total_iterations=total_iterations,
                extra_options=extra_scheduling_options,
            )

        return schedule

    def save_monthly_schedule(self):
        form_data = self.cleaned_data
        total_iterations = self.distill_total_iterations()
        content = self.distill_content()
        extra_scheduling_options = self.distill_extra_scheduling_options()

        positive_days = [day for day in form_data['days_of_month'] if day > 0]
        negative_days = [day for day in form_data['days_of_month'] if day < 0]
        sorted_days_of_month = sorted(positive_days) + sorted(negative_days)

        if self.initial_schedule:
            schedule = self.initial_schedule
            self.assert_timed_schedule(schedule)
            schedule.set_simple_monthly_schedule(
                self.distill_model_timed_event(),
                sorted_days_of_month,
                content,
                total_iterations=total_iterations,
                extra_options=extra_scheduling_options,
            )
        else:
            schedule = TimedSchedule.create_simple_monthly_schedule(
                self.domain,
                self.distill_model_timed_event(),
                sorted_days_of_month,
                content,
                total_iterations=total_iterations,
                extra_options=extra_scheduling_options,
            )

        return schedule

    def save_schedule(self):
        send_frequency = self.cleaned_data['send_frequency']
        return {
            self.SEND_IMMEDIATELY: self.save_immediate_schedule,
            self.SEND_DAILY: self.save_daily_schedule,
            self.SEND_WEEKLY: self.save_weekly_schedule,
            self.SEND_MONTHLY: self.save_monthly_schedule,
        }[send_frequency]()


class BroadcastForm(ScheduleForm):

    schedule_name = CharField(
        required=True,
        label=ugettext_lazy('Schedule Name'),
        max_length=1000,
    )

    start_date = CharField(
        label='',
        required=False
    )

    def __init__(self, domain, schedule, can_use_sms_surveys, broadcast, *args, **kwargs):
        self.initial_broadcast = broadcast
        super(BroadcastForm, self).__init__(domain, schedule, can_use_sms_surveys, *args, **kwargs)

    def get_layout_fields(self):
        result = super(BroadcastForm, self).get_layout_fields()
        result.append(
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _("Save"),
                    css_class='btn-primary',
                    type='submit',
                ),
            )
        )
        return result

    def get_start_date_layout_fields(self):
        return [
            hqcrispy.B3MultiField(
                _("Start"),
                crispy.Div(
                    twbscrispy.InlineField(
                        'start_date',
                        data_bind='value: start_date',
                    ),
                    css_class='col-sm-6',
                ),
                data_bind='visible: showStartDateInput',
            ),
        ]

    def get_scheduling_layout_fields(self):
        result = [
            crispy.Field('schedule_name'),
        ]
        result.extend(super(BroadcastForm, self).get_scheduling_layout_fields())
        return result

    def compute_initial(self):
        result = super(BroadcastForm, self).compute_initial()
        if self.initial_broadcast:
            result['schedule_name'] = self.initial_broadcast.name
            self.add_initial_recipients(self.initial_broadcast.recipients, result)
            if isinstance(self.initial_broadcast, ScheduledBroadcast):
                result['start_date'] = self.initial_broadcast.start_date.strftime('%Y-%m-%d')

        return result

    def clean_start_date(self):
        if self.cleaned_data.get('send_frequency') == self.SEND_IMMEDIATELY:
            return None

        return validate_date(self.cleaned_data.get('start_date'))

    def distill_start_offset(self):
        return 0

    def distill_start_day_of_week(self):
        if self.cleaned_data['send_frequency'] != self.SEND_WEEKLY:
            return TimedSchedule.ANY_DAY

        return self.cleaned_data['start_date'].weekday()

    def save_immediate_broadcast(self, schedule):
        form_data = self.cleaned_data
        recipients = self.distill_recipients()

        if self.initial_broadcast:
            raise ImmediateMessageEditAttempt("Cannot edit an ImmediateBroadcast")

        return ImmediateBroadcast.objects.create(
            domain=self.domain,
            name=form_data['schedule_name'],
            schedule=schedule,
            recipients=recipients,
        )

    def save_scheduled_broadcast(self, schedule):
        form_data = self.cleaned_data
        recipients = self.distill_recipients()

        if self.initial_broadcast:
            broadcast = self.initial_broadcast
            if not isinstance(broadcast, ScheduledBroadcast):
                raise TypeError("Expected ScheduledBroadcast")
        else:
            broadcast = ScheduledBroadcast(
                domain=self.domain,
                schedule=schedule,
            )

        broadcast.name = form_data['schedule_name']
        broadcast.start_date = form_data['start_date']
        broadcast.recipients = recipients
        broadcast.save()
        return broadcast

    def save_broadcast_and_schedule(self):
        with transaction.atomic():
            schedule = self.save_schedule()

            send_frequency = self.cleaned_data['send_frequency']
            broadcast = {
                self.SEND_IMMEDIATELY: self.save_immediate_broadcast,
                self.SEND_DAILY: self.save_scheduled_broadcast,
                self.SEND_WEEKLY: self.save_scheduled_broadcast,
                self.SEND_MONTHLY: self.save_scheduled_broadcast,
            }[send_frequency](schedule)

        return (broadcast, schedule)


class ConditionalAlertScheduleForm(ScheduleForm):
    START_DATE_RULE_TRIGGER = 'RULE_TRIGGER'
    START_DATE_CASE_PROPERTY = 'CASE_PROPERTY'
    START_DATE_FROM_VISIT_SCHEDULER = 'VISIT_SCHEDULER'

    START_OFFSET_ZERO = 'ZERO'
    START_OFFSET_NEGATIVE = 'NEGATIVE'
    START_OFFSET_POSITIVE = 'POSITIVE'

    YES = 'Y'
    NO = 'N'

    start_date_type = ChoiceField(
        required=True,
        choices=(
            (START_DATE_RULE_TRIGGER, ugettext_lazy("The first available time after the rule is satisfied")),
            (START_DATE_CASE_PROPERTY, ugettext_lazy("The date from case property: ")),
        )
    )

    start_date_case_property = TrimmedCharField(
        label='',
        required=False,
    )

    start_offset_type = ChoiceField(
        required=False,
        choices=(
            (START_OFFSET_ZERO, ugettext_lazy("Exactly on the start date")),
            (START_OFFSET_NEGATIVE, ugettext_lazy("Before the start date by")),
            (START_OFFSET_POSITIVE, ugettext_lazy("After the start date by")),
        )
    )

    start_offset = IntegerField(
        label='',
        required=False,
        min_value=1,
    )

    start_day_of_week = ChoiceField(
        required=False,
        choices=(
            ('6', ugettext_lazy('The first Sunday that occurs on or after the start date')),
            ('0', ugettext_lazy('The first Monday that occurs on or after the start date')),
            ('1', ugettext_lazy('The first Tuesday that occurs on or after the start date')),
            ('2', ugettext_lazy('The first Wednesday that occurs on or after the start date')),
            ('3', ugettext_lazy('The first Thursday that occurs on or after the start date')),
            ('4', ugettext_lazy('The first Friday that occurs on or after the start date')),
            ('5', ugettext_lazy('The first Saturday that occurs on or after the start date')),
        ),
    )

    custom_recipient = ChoiceField(
        required=False,
        choices=(
            (k, v[1])
            for k, v in settings.AVAILABLE_CUSTOM_SCHEDULING_RECIPIENTS.items()
        )
    )

    custom_sms_content_id = ChoiceField(
        required=False,
        label=ugettext_lazy("Custom SMS Content"),
        choices=((k, v[1]) for k, v in settings.AVAILABLE_CUSTOM_SCHEDULING_CONTENT.items()),
    )

    reset_case_property_enabled = ChoiceField(
        required=True,
        choices=(
            (NO, ugettext_lazy("Disabled")),
            (YES, ugettext_lazy("Restart schedule when this case property takes any new value: ")),
        ),
    )

    reset_case_property_name = TrimmedCharField(
        label='',
        required=False,
    )

    send_time_case_property_name = TrimmedCharField(
        label='',
        required=False,
    )

    visit_scheduler_form_unique_id = CharField(
        label=ugettext_lazy("Scheduler: Form"),
        required=False,
    )

    visit_number = IntegerField(
        label='',
        required=False,
        min_value=1,
    )

    visit_window_position = ChoiceField(
        label=ugettext_lazy("Scheduler: Use"),
        required=False,
        choices=(
            (VISIT_WINDOW_START, ugettext_lazy("the first date in the visit window")),
            (VISIT_WINDOW_DUE_DATE, ugettext_lazy("the due date of the visit")),
            (VISIT_WINDOW_END, ugettext_lazy("the last date in the visit window")),
        ),
    )

    capture_custom_metadata_item = ChoiceField(
        label='',
        choices=(
            (NO, ugettext_lazy("No")),
            (YES, ugettext_lazy("Yes")),
        ),
        required=False,
    )

    custom_metadata_item_name = TrimmedCharField(
        label=ugettext_lazy("Custom Data: Name"),
        required=False,
    )

    custom_metadata_item_value = TrimmedCharField(
        label=ugettext_lazy("Custom Data: Value"),
        required=False,
    )

    def __init__(self, domain, schedule, can_use_sms_surveys, rule, criteria_form, *args, **kwargs):
        self.initial_rule = rule
        self.criteria_form = criteria_form
        super(ConditionalAlertScheduleForm, self).__init__(domain, schedule, can_use_sms_surveys, *args, **kwargs)
        if self.initial_rule:
            self.set_read_only_fields_during_editing()
        self.update_recipient_types_choices()
        self.update_send_time_type_choices()
        self.update_start_date_type_choices()

    def get_extra_timing_fields(self):
        return [
            crispy.Div(
                twbscrispy.InlineField('send_time_case_property_name'),
                data_bind="visible: send_time_type() === '%s'" % TimedSchedule.EVENT_CASE_PROPERTY_TIME,
                css_class='col-sm-6',
            ),
        ]

    def add_initial_for_content(self, result):
        content = self.initial_schedule.memoized_events[0].content
        if isinstance(content, CustomContent):
            result['content'] = self.CONTENT_CUSTOM_SMS
            result['custom_sms_content_id'] = content.custom_content_id
        else:
            return super(ConditionalAlertScheduleForm, self).add_initial_for_content(result)

    def add_additional_content_types(self):
        super(ConditionalAlertScheduleForm, self).add_additional_content_types()

        if (
            self.criteria_form.is_system_admin or
            self.initial.get('content') == self.CONTENT_CUSTOM_SMS
        ):
            self.fields['content'].choices += [
                (self.CONTENT_CUSTOM_SMS, _("Custom SMS")),
            ]

    @property
    def current_visit_scheduler_form(self):
        value = self['visit_scheduler_form_unique_id'].value()
        if not value:
            return {}

        try:
            form, app = self.get_latest_released_form_and_app(value)
        except:
            return {}

        return {'id': form.unique_id, 'text': form.full_path_name}

    @property
    def scheduling_fieldset_legend(self):
        return ''

    def set_read_only_fields_during_editing(self):
        # Django also handles keeping the field's value to its initial value no matter what is posted
        # https://docs.djangoproject.com/en/1.11/ref/forms/fields/#disabled

        # Don't allow the reset_case_property_name to change values after being initially set.
        # The framework doesn't account for this option being enabled, disabled, or changing
        # after being initially set.
        self.fields['reset_case_property_enabled'].disabled = True
        self.fields['reset_case_property_name'].disabled = True

    @cached_property
    def requires_system_admin_to_edit(self):
        return (
            CaseScheduleInstanceMixin.RECIPIENT_TYPE_CUSTOM in self.initial.get('recipient_types', []) or
            self.initial.get('content') == self.CONTENT_CUSTOM_SMS or
            self.initial.get('start_date_type') == self.START_DATE_FROM_VISIT_SCHEDULER or
            self.initial.get('capture_custom_metadata_item') == self.YES
        )

    @cached_property
    def requires_system_admin_to_save(self):
        return (
            CaseScheduleInstanceMixin.RECIPIENT_TYPE_CUSTOM in self.cleaned_data['recipient_types'] or
            self.cleaned_data['content'] == self.CONTENT_CUSTOM_SMS or
            self.cleaned_data['start_date_type'] == self.START_DATE_FROM_VISIT_SCHEDULER or
            self.cleaned_data['capture_custom_metadata_item'] == self.YES
        )

    def update_send_time_type_choices(self):
        self.fields['send_time_type'].choices += [
            (TimedSchedule.EVENT_CASE_PROPERTY_TIME, _("The time from case property:")),
        ]

    def update_recipient_types_choices(self):
        new_choices = [
            (CaseScheduleInstanceMixin.RECIPIENT_TYPE_SELF, _("The Case")),
            (CaseScheduleInstanceMixin.RECIPIENT_TYPE_CASE_OWNER, _("The Case's Owner")),
        ]
        new_choices.extend(self.fields['recipient_types'].choices)

        if (
            self.criteria_form.is_system_admin or
            CaseScheduleInstanceMixin.RECIPIENT_TYPE_CUSTOM in self.initial.get('recipient_types', [])
        ):
            new_choices.extend([
                (CaseScheduleInstanceMixin.RECIPIENT_TYPE_CUSTOM, _("Custom Recipient")),
            ])

        self.fields['recipient_types'].choices = new_choices

    def update_start_date_type_choices(self):
        if (
            self.criteria_form.is_system_admin or
            self.initial.get('start_date_type') == self.START_DATE_FROM_VISIT_SCHEDULER
        ):
            self.fields['start_date_type'].choices += [
                (self.START_DATE_FROM_VISIT_SCHEDULER, _("A date from a visit scheduler")),
            ]

    def add_initial_for_send_time(self, initial):
        if self.initial_schedule.event_type == TimedSchedule.EVENT_CASE_PROPERTY_TIME:
            initial['send_time_case_property_name'] = \
                self.initial_schedule.memoized_events[0].case_property_name
        else:
            super(ConditionalAlertScheduleForm, self).add_initial_for_send_time(initial)

    def add_initial_recipients(self, recipients, initial):
        super(ConditionalAlertScheduleForm, self).add_initial_recipients(recipients, initial)

        for recipient_type, recipient_id in recipients:
            if recipient_type == CaseScheduleInstanceMixin.RECIPIENT_TYPE_CUSTOM:
                initial['custom_recipient'] = recipient_id

    def add_initial_for_custom_metadata(self, result):
        if (
            isinstance(self.initial_schedule.custom_metadata, dict) and
            len(self.initial_schedule.custom_metadata) > 0
        ):
            result['capture_custom_metadata_item'] = self.YES
            for name, value in self.initial_schedule.custom_metadata.items():
                result['custom_metadata_item_name'] = name
                result['custom_metadata_item_value'] = value
                # We only capture one item right now, but the framework allows
                # capturing any number of name, value pairs
                break

    def compute_initial(self):
        result = super(ConditionalAlertScheduleForm, self).compute_initial()
        if self.initial_schedule:
            schedule = self.initial_schedule
            if isinstance(schedule, TimedSchedule):
                if schedule.start_offset == 0:
                    result['start_offset_type'] = self.START_OFFSET_ZERO
                elif schedule.start_offset > 0:
                    result['start_offset_type'] = self.START_OFFSET_POSITIVE
                    result['start_offset'] = schedule.start_offset
                else:
                    result['start_offset_type'] = self.START_OFFSET_NEGATIVE
                    result['start_offset'] = abs(schedule.start_offset)

                if schedule.start_day_of_week >= 0:
                    result['start_day_of_week'] = str(schedule.start_day_of_week)

            self.add_initial_for_custom_metadata(result)

        if self.initial_rule:
            action_definition = self.initial_rule.memoized_actions[0].definition
            self.add_initial_recipients(action_definition.recipients, result)
            if action_definition.reset_case_property_name:
                result['reset_case_property_enabled'] = self.YES
                result['reset_case_property_name'] = action_definition.reset_case_property_name
            else:
                result['reset_case_property_enabled'] = self.NO

            scheduler_module_info = action_definition.get_scheduler_module_info()
            if action_definition.start_date_case_property:
                result['start_date_type'] = self.START_DATE_CASE_PROPERTY
                result['start_date_case_property'] = action_definition.start_date_case_property
            elif scheduler_module_info.enabled:
                result['visit_scheduler_form_unique_id'] = scheduler_module_info.form_unique_id
                result['start_date_type'] = self.START_DATE_FROM_VISIT_SCHEDULER

                # Convert to 1-based index for display as in the form builder
                result['visit_number'] = scheduler_module_info.visit_number + 1
                result['visit_window_position'] = scheduler_module_info.window_position
            else:
                result['start_date_type'] = self.START_DATE_RULE_TRIGGER

        return result

    def get_start_date_layout_fields(self):
        return [
            hqcrispy.B3MultiField(
                _("Start Date"),
                crispy.Div(
                    twbscrispy.InlineField(
                        'start_date_type',
                        data_bind='value: start_date_type',
                    ),
                    css_class='col-sm-8',
                ),
                crispy.Div(
                    twbscrispy.InlineField(
                        'start_date_case_property',
                    ),
                    data_bind="visible: start_date_type() === '%s'" % self.START_DATE_CASE_PROPERTY,
                    css_class='col-sm-4',
                ),
                crispy.Div(
                    self.get_system_admin_label(),
                    data_bind="visible: start_date_type() === '%s'" % self.START_DATE_FROM_VISIT_SCHEDULER,
                ),
                data_bind='visible: showStartDateInput',
            ),
            crispy.Div(
                crispy.Field('visit_scheduler_form_unique_id'),
                hqcrispy.B3MultiField(
                    _("Scheduler: Visit"),
                    crispy.Div(
                        twbscrispy.InlineField('visit_number'),
                        css_class='col-sm-4',
                    ),
                ),
                crispy.Field('visit_window_position'),
                data_bind="visible: start_date_type() === '%s'" % self.START_DATE_FROM_VISIT_SCHEDULER,
            ),
            hqcrispy.B3MultiField(
                _("Begin"),
                crispy.Div(
                    twbscrispy.InlineField(
                        'start_offset_type',
                        data_bind='value: start_offset_type',
                    ),
                    css_class='col-sm-4',
                ),
                crispy.Div(
                    twbscrispy.InlineField('start_offset'),
                    css_class='col-sm-2',
                    data_bind="visible: start_offset_type() !== '%s'" % self.START_OFFSET_ZERO,
                ),
                crispy.Div(
                    crispy.HTML("<span>%s</span>" % _("day(s)")),
                    data_bind="visible: start_offset_type() !== '%s'" % self.START_OFFSET_ZERO,
                ),
                data_bind="visible: send_frequency() === '%s'" % self.SEND_DAILY,
            ),
            hqcrispy.B3MultiField(
                _("Begin"),
                twbscrispy.InlineField('start_day_of_week'),
                data_bind="visible: send_frequency() === '%s'" % self.SEND_WEEKLY,
            ),
        ]

    def get_recipients_layout_fields(self):
        result = super(ConditionalAlertScheduleForm, self).get_recipients_layout_fields()
        result.extend([
            hqcrispy.B3MultiField(
                _("Custom Recipient"),
                twbscrispy.InlineField('custom_recipient'),
                self.get_system_admin_label(),
                data_bind="visible: recipientTypeSelected('%s')" % CaseScheduleInstanceMixin.RECIPIENT_TYPE_CUSTOM,
            ),
        ])
        return result

    def get_content_layout_fields(self):
        result = super(ConditionalAlertScheduleForm, self).get_content_layout_fields()
        result.extend([
            hqcrispy.B3MultiField(
                _("Custom SMS Content"),
                twbscrispy.InlineField('custom_sms_content_id'),
                self.get_system_admin_label(),
                data_bind="visible: content() === '%s'" % self.CONTENT_CUSTOM_SMS,
            ),
        ])
        return result

    def get_advanced_layout_fields(self):
        result = super(ConditionalAlertScheduleForm, self).get_advanced_layout_fields()
        result.extend([
            hqcrispy.B3MultiField(
                _("Restart Schedule"),
                crispy.Div(
                    twbscrispy.InlineField(
                        'reset_case_property_enabled',
                        data_bind='value: reset_case_property_enabled',
                    ),
                    css_class='col-sm-8',
                ),
                crispy.Div(
                    twbscrispy.InlineField(
                        'reset_case_property_name',
                        placeholder=_("case property"),
                    ),
                    data_bind="visible: reset_case_property_enabled() === '%s'" % self.YES,
                    css_class='col-sm-4',
                ),
            ),
        ])

        if (
            self.criteria_form.is_system_admin or
            self.initial.get('capture_custom_metadata_item') == self.YES
        ):
            result.extend([
                hqcrispy.B3MultiField(
                    _("Capture Custom Data on each SMS"),
                    crispy.Div(
                        twbscrispy.InlineField(
                            'capture_custom_metadata_item',
                            data_bind='value: capture_custom_metadata_item',
                        ),
                        css_class='col-sm-4',
                    ),
                    crispy.Div(
                        self.get_system_admin_label(),
                        data_bind="visible: capture_custom_metadata_item() === 'Y'",
                    ),
                ),
                crispy.Div(
                    crispy.Field('custom_metadata_item_name'),
                    crispy.Field('custom_metadata_item_value'),
                    data_bind="visible: capture_custom_metadata_item() === 'Y'",
                ),
            ])

        return result

    def get_system_admin_label(self):
        return crispy.HTML("""
            <label class="col-xs-1 control-label">
                <span class="label label-primary">%s</span>
            </label>
        """ % _("Requires System Admin"))

    def clean_start_offset_type(self):
        if self.cleaned_data.get('send_frequency') != self.SEND_DAILY:
            return None

        value = self.cleaned_data.get('start_offset_type')

        if not value:
            raise ValidationError(_("This field is required"))

        if (
            value == self.START_OFFSET_NEGATIVE and
            self.cleaned_data.get('start_date_type') == self.START_DATE_RULE_TRIGGER
        ):
            raise ValidationError(_("You may not start sending before the day that the rule triggers."))

        return value

    def clean_start_day_of_week(self):
        if self.cleaned_data.get('send_frequency') != self.SEND_WEEKLY:
            return TimedSchedule.ANY_DAY

        value = self.cleaned_data.get('start_day_of_week')
        error = ValidationError(_("Invalid choice selected"))

        try:
            value = int(value)
        except (ValueError, TypeError):
            raise error

        if value < 0 or value > 6:
            raise error

        return value

    def clean_custom_recipient(self):
        recipient_types = self.cleaned_data.get('recipient_types', [])
        custom_recipient = self.cleaned_data.get('custom_recipient')

        if CaseScheduleInstanceMixin.RECIPIENT_TYPE_CUSTOM not in recipient_types:
            return None

        if not custom_recipient:
            raise ValidationError(_("This field is required"))

        return custom_recipient

    def clean_custom_sms_content_id(self):
        if self.cleaned_data['content'] != self.CONTENT_CUSTOM_SMS:
            return None

        value = self.cleaned_data['custom_sms_content_id']
        if not value:
            raise ValidationError(_("This field is required"))

        return value

    def clean_reset_case_property_enabled(self):
        value = self.cleaned_data['reset_case_property_enabled']
        if (
            value == self.YES and
            self.cleaned_data.get('send_frequency') != self.SEND_IMMEDIATELY and
            self.cleaned_data.get('start_date_type') != self.START_DATE_RULE_TRIGGER
        ):
            raise ValidationError(
                _("This option can only be enabled when the schedule's start "
                  "date is the date that the rule triggers.")
            )

        return value

    def clean_reset_case_property_name(self):
        if self.cleaned_data.get('reset_case_property_enabled') == self.NO:
            return None

        return validate_case_property_name(
            self.cleaned_data.get('reset_case_property_name'),
            allow_parent_case_references=False,
        )

    def clean_start_date_case_property(self):
        if (
            self.cleaned_data.get('send_frequency') == self.SEND_IMMEDIATELY or
            self.cleaned_data.get('start_date_type') != self.START_DATE_CASE_PROPERTY
        ):
            return None

        return validate_case_property_name(
            self.cleaned_data.get('start_date_case_property'),
            allow_parent_case_references=False,
        )

    def clean_send_time_case_property_name(self):
        if (
            self.cleaned_data.get('send_frequency') == self.SEND_IMMEDIATELY or
            self.cleaned_data.get('send_time_type') != TimedSchedule.EVENT_CASE_PROPERTY_TIME
        ):
            return None

        return validate_case_property_name(
            self.cleaned_data.get('send_time_case_property_name'),
            allow_parent_case_references=False,
        )

    def clean_visit_scheduler_form_unique_id(self):
        if self.cleaned_data.get('start_date_type') != self.START_DATE_FROM_VISIT_SCHEDULER:
            return None

        value = self.cleaned_data.get('visit_scheduler_form_unique_id')
        if not value:
            raise ValidationError(_("This field is required"))

        form, app = self.get_latest_released_form_and_app(value)
        if isinstance(form, AdvancedForm) and form.schedule and form.schedule.enabled:
            return value

        raise ValidationError(_("Please select a visit scheduler form"))

    def clean_visit_number(self):
        if self.cleaned_data.get('start_date_type') != self.START_DATE_FROM_VISIT_SCHEDULER:
            return None

        form_unique_id = self.cleaned_data.get('visit_scheduler_form_unique_id')
        if not form_unique_id:
            raise ValidationError(_("Please first select a visit scheduler form"))

        value = self.cleaned_data.get('visit_number')
        if value is None or value <= 0:
            raise ValidationError(_("Please enter a number greater than 0"))

        visit_index = value - 1

        form, app = self.get_latest_released_form_and_app(form_unique_id)
        try:
            visit = form.schedule.visits[visit_index]
        except IndexError:
            raise ValidationError(
                _("Visit number not found in latest released app build. Please check form configuration.")
            )

        if visit.repeats:
            raise ValidationError(
                _("The referenced visit in the latest released app build is a repeat visit. "
                  "Repeat visits are not supported")
            )

        if not isinstance(visit.expires, int):
            raise ValidationError(
                _("The referenced visit in the latest released app build does not have a window end date. "
                  "Visits which do not have a window end date are not supported")
            )

        return value

    def clean_visit_window_position(self):
        if self.cleaned_data.get('start_date_type') != self.START_DATE_FROM_VISIT_SCHEDULER:
            return None

        value = self.cleaned_data.get('visit_window_position')
        if not value:
            raise ValidationError("This field is required")

        return value

    def clean_custom_metadata_item_name(self):
        if self.cleaned_data.get('capture_custom_metadata_item') != self.YES:
            return None

        value = self.cleaned_data.get('custom_metadata_item_name')
        if not value:
            raise ValidationError(_("This field is required."))

        return value

    def clean_custom_metadata_item_value(self):
        if self.cleaned_data.get('capture_custom_metadata_item') != self.YES:
            return None

        value = self.cleaned_data.get('custom_metadata_item_value')
        if not value:
            raise ValidationError(_("This field is required."))

        return value

    def distill_start_offset(self):
        send_frequency = self.cleaned_data.get('send_frequency')
        start_offset_type = self.cleaned_data.get('start_offset_type')

        if (
            send_frequency == self.SEND_DAILY and
            start_offset_type in (self.START_OFFSET_NEGATIVE, self.START_OFFSET_POSITIVE)
        ):

            start_offset = self.cleaned_data.get('start_offset')

            if start_offset is None:
                raise ValidationError(_("This field is required"))

            if start_offset_type == self.START_OFFSET_NEGATIVE:
                return -1 * start_offset
            else:
                return start_offset

        return 0

    def distill_start_day_of_week(self):
        return self.cleaned_data['start_day_of_week']

    def distill_scheduler_module_info(self):
        if self.cleaned_data.get('start_date_type') != self.START_DATE_FROM_VISIT_SCHEDULER:
            return CreateScheduleInstanceActionDefinition.SchedulerModuleInfo(enabled=False)

        form_unique_id = self.cleaned_data['visit_scheduler_form_unique_id']
        form, app = self.get_form_and_app(form_unique_id)
        return CreateScheduleInstanceActionDefinition.SchedulerModuleInfo(
            enabled=True,
            # The id of the primary application doc
            app_id=app.get_id,
            form_unique_id=form_unique_id,
            # Convert to 0-based index
            visit_number=self.cleaned_data['visit_number'] - 1,
            window_position=self.cleaned_data['visit_window_position'],
        )

    def distill_recipients(self):
        result = super(ConditionalAlertScheduleForm, self).distill_recipients()
        recipient_types = self.cleaned_data['recipient_types']

        if CaseScheduleInstanceMixin.RECIPIENT_TYPE_SELF in recipient_types:
            result.append((CaseScheduleInstanceMixin.RECIPIENT_TYPE_SELF, None))

        if CaseScheduleInstanceMixin.RECIPIENT_TYPE_CASE_OWNER in recipient_types:
            result.append((CaseScheduleInstanceMixin.RECIPIENT_TYPE_CASE_OWNER, None))

        if CaseScheduleInstanceMixin.RECIPIENT_TYPE_CUSTOM in recipient_types:
            custom_recipient_id = self.cleaned_data['custom_recipient']
            result.append((CaseScheduleInstanceMixin.RECIPIENT_TYPE_CUSTOM, custom_recipient_id))

        return result

    def distill_content(self):
        if self.cleaned_data['content'] == self.CONTENT_CUSTOM_SMS:
            return CustomContent(
                custom_content_id=self.cleaned_data['custom_sms_content_id']
            )
        else:
            return super(ConditionalAlertScheduleForm, self).distill_content()

    def distill_model_timed_event(self):
        event_type = self.cleaned_data['send_time_type']
        if event_type == TimedSchedule.EVENT_CASE_PROPERTY_TIME:
            return CasePropertyTimedEvent(
                case_property_name=self.cleaned_data['send_time_case_property_name'],
            )

        return super(ConditionalAlertScheduleForm, self).distill_model_timed_event()

    def distill_extra_scheduling_options(self):
        extra_options = super(ConditionalAlertScheduleForm, self).distill_extra_scheduling_options()

        if self.cleaned_data.get('capture_custom_metadata_item') == self.YES:
            extra_options['custom_metadata'] = {
                self.cleaned_data['custom_metadata_item_name']: self.cleaned_data['custom_metadata_item_value']
            }
        else:
            extra_options['custom_metadata'] = {}

        return extra_options

    def create_rule_action(self, rule, schedule):
        fields = {
            'recipients': self.distill_recipients(),
            'reset_case_property_name': self.cleaned_data['reset_case_property_name'],
            'scheduler_module_info': self.distill_scheduler_module_info().to_json(),
            'start_date_case_property': self.cleaned_data['start_date_case_property'],
        }

        if isinstance(schedule, AlertSchedule):
            fields['alert_schedule'] = schedule
        elif isinstance(schedule, TimedSchedule):
            fields['timed_schedule'] = schedule
        else:
            raise TypeError("Unexpected Schedule type")

        rule.add_action(CreateScheduleInstanceActionDefinition, **fields)

    def edit_rule_action(self, rule, schedule):
        action = rule.caseruleaction_set.all()[0]
        action_definition = action.definition
        self.validate_existing_action_definition(action_definition, schedule)

        action_definition.recipients = self.distill_recipients()
        action_definition.reset_case_property_name = self.cleaned_data['reset_case_property_name']
        action_definition.set_scheduler_module_info(self.distill_scheduler_module_info())
        action_definition.start_date_case_property = self.cleaned_data['start_date_case_property']
        action_definition.save()

    def validate_existing_action_definition(self, action_definition, schedule):
        if not isinstance(action_definition, CreateScheduleInstanceActionDefinition):
            raise TypeError("Expected CreateScheduleInstanceActionDefinition")

        if isinstance(schedule, AlertSchedule):
            if action_definition.alert_schedule_id != schedule.schedule_id:
                raise ValueError("Schedule mismatch")
        elif isinstance(schedule, TimedSchedule):
            if action_definition.timed_schedule_id != schedule.schedule_id:
                raise ValueError("Schedule mismatch")
        else:
            raise TypeError("Unexpected Schedule type")

    def save_rule_action(self, rule, schedule):
        num_actions = rule.caseruleaction_set.count()
        if num_actions == 0:
            self.create_rule_action(rule, schedule)
        elif num_actions == 1:
            self.edit_rule_action(rule, schedule)
        else:
            raise ValueError("Expected 0 or 1 action")

    def save_rule_action_and_schedule(self, rule):
        with transaction.atomic():
            schedule = self.save_schedule()
            self.save_rule_action(rule, schedule)


class ConditionalAlertForm(Form):
    # Prefix to avoid name collisions; this means all input
    # names in the HTML are prefixed with "conditional-alert-"
    prefix = "conditional-alert"

    name = TrimmedCharField(
        label=ugettext_lazy("Name"),
        required=True,
    )

    def __init__(self, domain, rule, *args, **kwargs):
        self.domain = domain
        self.initial_rule = rule

        if kwargs.get('initial'):
            raise ValueError("Initial values are set by the form")

        if self.initial_rule:
            kwargs['initial'] = self.compute_initial()

        super(ConditionalAlertForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.label_class = 'col-xs-2 col-xs-offset-1'
        self.helper.field_class = 'col-xs-2'
        self.helper.form_tag = False

        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                "",
                crispy.Field('name'),
            ),
        )

    def compute_initial(self):
        return {
            'name': self.initial_rule.name,
        }


class ConditionalAlertCriteriaForm(CaseRuleCriteriaForm):

    @property
    def show_fieldset_title(self):
        return False

    @property
    def fieldset_help_text(self):
        return _("An instance of the schedule will be created for each case matching all filter criteria below.")

    @property
    def allow_parent_case_references(self):
        return False

    @property
    def allow_case_modified_filter(self):
        return False

    @property
    def allow_case_property_filter(self):
        return True

    @property
    def allow_date_case_property_filter(self):
        return False

    def set_read_only_fields_during_editing(self):
        # Django also handles keeping the field's value to its initial value no matter what is posted
        # https://docs.djangoproject.com/en/1.11/ref/forms/fields/#disabled

        # Prevent case_type from being changed when we are using the form to edit
        # an existing conditional alert. Being allowed to assume that case_type
        # doesn't change makes it easier to run the rule for this alert.
        self.fields['case_type'].disabled = True

    def __init__(self, *args, **kwargs):
        super(ConditionalAlertCriteriaForm, self).__init__(*args, **kwargs)
        if self.initial_rule:
            self.set_read_only_fields_during_editing()
