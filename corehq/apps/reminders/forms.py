import copy
import json
import re
from couchdbkit import ResourceNotFound
from crispy_forms.bootstrap import InlineField, FormActions, StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy
from django.core.urlresolvers import reverse
from django.template.loader import render_to_string
import pytz
from datetime import timedelta, datetime, time, date
from django.conf import settings
from django.core.exceptions import ValidationError
from django.forms.fields import *
from django.forms.forms import Form
from django.forms.widgets import CheckboxSelectMultiple
from django import forms
from django.forms import Field, Widget
from corehq.apps.casegroups.models import CommCareCaseGroup
from corehq.apps.casegroups.dbaccessors import get_case_groups_in_domain
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.util import get_locations_from_ids
from corehq.apps.reminders.util import DotExpandedDict, get_form_list
from corehq.apps.groups.models import Group
from corehq.apps.hqwebapp.crispy import (
    BootstrapMultiField, FieldsetAccordionGroup, HiddenFieldWithErrors,
    FieldWithHelpBubble, InlineColumnField, ErrorsOnlyField,
)
from corehq.apps.users.forms import SupplyPointSelectWidget
from corehq import toggles
from corehq.util.spreadsheets.excel import WorksheetNotFound, \
    WorkbookJSONReader
from corehq.util.timezones.conversions import UserTime
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.decorators.memoized import memoized
from .models import (
    REPEAT_SCHEDULE_INDEFINITELY,
    CaseReminderEvent,
    RECIPIENT_USER,
    RECIPIENT_CASE,
    RECIPIENT_SURVEY_SAMPLE,
    RECIPIENT_OWNER,
    RECIPIENT_LOCATION,
    MATCH_EXACT,
    MATCH_REGEX,
    MATCH_ANY_VALUE,
    EVENT_AS_SCHEDULE,
    EVENT_AS_OFFSET,
    CaseReminderHandler,
    FIRE_TIME_DEFAULT,
    FIRE_TIME_CASE_PROPERTY,
    METHOD_SMS,
    METHOD_SMS_CALLBACK,
    METHOD_SMS_SURVEY,
    METHOD_IVR_SURVEY,
    METHOD_EMAIL,
    CASE_CRITERIA,
    QUESTION_RETRY_CHOICES,
    SurveyKeyword,
    RECIPIENT_PARENT_CASE,
    RECIPIENT_SUBCASE,
    FIRE_TIME_RANDOM,
    ON_DATETIME,
    SEND_NOW,
    SEND_LATER,
    RECIPIENT_USER_GROUP,
    UI_SIMPLE_FIXED,
    UI_COMPLEX,
    RECIPIENT_ALL_SUBCASES,
    DAY_MON,
    DAY_TUE,
    DAY_WED,
    DAY_THU,
    DAY_FRI,
    DAY_SAT,
    DAY_SUN,
    DAY_ANY,
)
from dimagi.utils.parsing import string_to_datetime
from corehq.util.timezones.forms import TimeZoneChoiceField
from dateutil.parser import parse
from openpyxl.utils.exceptions import InvalidFileException
from django.utils.translation import ugettext as _, ugettext_noop, ugettext_lazy
from corehq.apps.app_manager.models import Form as CCHQForm
from dimagi.utils.django.fields import TrimmedCharField
from corehq.util.timezones.utils import get_timezone_for_user
from langcodes import get_name as get_language_name

ONE_MINUTE_OFFSET = time(0, 1)

NO_RESPONSE = "none"

YES_OR_NO = (
    ("Y", ugettext_lazy("Yes")),
    ("N", ugettext_lazy("No")),
)

NOW_OR_LATER = (
    (SEND_NOW, ugettext_lazy("Now")),
    (SEND_LATER, ugettext_lazy("Later")),
)

CONTENT_CHOICES = (
    (METHOD_SMS, ugettext_lazy("SMS")),
    (METHOD_SMS_SURVEY, ugettext_lazy("SMS Survey")),
)

KEYWORD_CONTENT_CHOICES = (
    (METHOD_SMS, ugettext_lazy("SMS")),
    (METHOD_SMS_SURVEY, ugettext_lazy("SMS Survey")),
    (NO_RESPONSE, ugettext_lazy("No Response")),
)

KEYWORD_RECIPIENT_CHOICES = (
    (RECIPIENT_USER_GROUP, ugettext_lazy("Mobile Worker Group")),
    (RECIPIENT_OWNER, ugettext_lazy("The case's owner")),
)

ONE_TIME_RECIPIENT_CHOICES = (
    (RECIPIENT_USER_GROUP, ugettext_lazy("Mobile Worker Group")),
    (RECIPIENT_SURVEY_SAMPLE, ugettext_lazy("Case Group")),
)

EVENT_CHOICES = (
    (EVENT_AS_OFFSET, ugettext_lazy("Offset-based")),
    (EVENT_AS_SCHEDULE, ugettext_lazy("Schedule-based"))
)


def add_field_choices(form, field_name, choice_tuples):
    choices = copy.copy(form.fields[field_name].choices)
    choices.extend(choice_tuples)
    form.fields[field_name].choices = choices


def user_group_choices(domain):
    ids = Group.ids_by_domain(domain)
    return [(doc['_id'], doc['name'])
            for doc in iter_docs(Group.get_db(), ids)]


def case_group_choices(domain):
    return [(group._id, group.name)
            for group in get_case_groups_in_domain(domain)]


def form_choices(domain):
    available_forms = get_form_list(domain)
    return [(form['code'], form['name']) for form in available_forms]


def validate_integer(value, error_msg, nonnegative=False):
    try:
        assert value is not None
        value = int(value)
        if nonnegative:
            assert value >= 0
        return value
    except (ValueError, AssertionError):
        raise ValidationError(error_msg)


def validate_date(value):
    date_regex = re.compile('^\d\d\d\d-\d\d-\d\d$')
    if not isinstance(value, basestring) or date_regex.match(value) is None:
        raise ValidationError(_('Dates must be in YYYY-MM-DD format.'))
    try:
        return parse(value).date()
    except Exception:
        raise ValidationError(_('Invalid date given.'))


def validate_time(value):
    if isinstance(value, time):
        return value
    error_msg = _("Please enter a valid time from 00:00 to 23:59.")
    time_regex = re.compile("^\d{1,2}:\d\d(:\d\d){0,1}$")
    if not isinstance(value, basestring) or time_regex.match(value) is None:
        raise ValidationError(error_msg)
    try:
        return parse(value).time()
    except Exception:
        raise ValidationError(error_msg)


def validate_form_unique_id(form_unique_id, domain):
    error_msg = _('Invalid form chosen.')
    try:
        form = CCHQForm.get_form(form_unique_id)
        app = form.get_app()
    except Exception:
        raise ValidationError(error_msg)

    if app.domain != domain:
        raise ValidationError(error_msg)

    return form_unique_id


def clean_group_id(group_id, expected_domain):
    error_msg = _('Invalid selection.')
    if not group_id:
        raise ValidationError(error_msg)

    try:
        group = Group.get(group_id)
    except Exception:
        raise ValidationError(error_msg)

    if group.doc_type != 'Group' or group.domain != expected_domain:
        raise ValidationError(error_msg)

    return group_id


def clean_case_group_id(group_id, expected_domain):
    error_msg = _('Invalid selection.')
    if not group_id:
        raise ValidationError(error_msg)

    try:
        group = CommCareCaseGroup.get(group_id)
    except Exception:
        raise ValidationError(error_msg)

    if group.doc_type != 'CommCareCaseGroup' or group.domain != expected_domain:
        raise ValidationError(error_msg)

    return group_id


# Used for validating the phone number from a UI. Returns the phone number if valid, otherwise raises a ValidationError.
def validate_phone_number(value):
    error_msg = _("Phone numbers must consist only of digits and must be in international format.")
    if not isinstance(value, basestring):
        # Cast to an int, then a str. Needed for excel upload where the field comes back as a float.
        try:
            value = str(int(value))
        except Exception:
            raise ValidationError(error_msg)
    
    value = value.strip()
    phone_regex = re.compile("^\d+$")
    if phone_regex.match(value) is None:
        raise ValidationError(error_msg)
    
    if isinstance(value, unicode):
        value = str(value)
    
    return value


MATCH_TYPE_CHOICES = (
    (MATCH_ANY_VALUE, ugettext_noop("exists.")),
    (MATCH_EXACT, ugettext_noop("equals")),
    (MATCH_REGEX, ugettext_noop("matches regular expression")),
)

START_REMINDER_ALL_CASES = 'start_all_cases'
START_REMINDER_ON_CASE_DATE = 'case_date'
START_REMINDER_ON_CASE_PROPERTY = 'case_property'
START_REMINDER_ON_DAY_OF_WEEK = 'day_of_week'

START_DATE_OFFSET_BEFORE = 'offset_before'
START_DATE_OFFSET_AFTER = 'offset_after'

START_PROPERTY_OFFSET_DELAY = 'offset_delay'
START_PROPERTY_OFFSET_IMMEDIATE = 'offset_immediate'

START_PROPERTY_ALL_CASES_VALUE = '_id'

EVENT_TIMING_IMMEDIATE = 'immediate'

REPEAT_TYPE_NO = 'no_repeat'
REPEAT_TYPE_INDEFINITE = 'indefinite'
REPEAT_TYPE_SPECIFIC = 'specific'

STOP_CONDITION_CASE_PROPERTY = 'case_property'


class BaseScheduleCaseReminderForm(forms.Form):
    """
    This form creates a new CaseReminder. It is the most basic version, no advanced options (like language).
    """
    nickname = forms.CharField(
        label=ugettext_noop("Name"),
        error_messages={
            'required': ugettext_noop("Please enter a name for this reminder."),
        }
    )

    # Fieldset: Send Options
    # simple has start_condition_type = CASE_CRITERIA by default
    case_type = forms.CharField(
        required=False,
        label=ugettext_noop("Send For Case Type"),
    )
    start_reminder_on = forms.ChoiceField(
        label=ugettext_noop("Send Reminder For"),
        required=False,
        choices=(
            (START_REMINDER_ALL_CASES, ugettext_noop("All Cases")),
            (START_REMINDER_ON_CASE_PROPERTY, ugettext_noop("Only Cases in Following State")),
        ),
    )
    ## send options > start_reminder_on = case_date
    start_property = forms.CharField(
        required=False,
        label=ugettext_noop("Enter a Case Property"),
    )
    start_match_type = forms.ChoiceField(
        required=False,
        choices=MATCH_TYPE_CHOICES,
    )
    # only shows up if start_match_type != MATCH_ANY_VALUE
    start_value = forms.CharField(
        required=False,
        label=ugettext_noop("Value")
    )
    # this is a UI control that determines how start_offset is calculated (0 or an integer)
    start_property_offset_type = forms.ChoiceField(
        required=False,
        choices=(
            (START_PROPERTY_OFFSET_IMMEDIATE, ugettext_noop("Immediately")),
            (START_PROPERTY_OFFSET_DELAY, ugettext_noop("Delay By")),
            (START_REMINDER_ON_CASE_DATE, ugettext_noop("Date in Case")),
            (START_REMINDER_ON_DAY_OF_WEEK, ugettext_noop("Specific Day of Week")),
        )
    )
    # becomes start_offset
    start_property_offset = forms.IntegerField(
        required=False,
        initial=1,
    )
    ## send options > start_reminder_on = case_property
    start_date = forms.CharField(
        required=False,
        label=ugettext_noop("Enter a Case Property"),
    )
    start_date_offset_type = forms.ChoiceField(
        required=False,
        choices=(
            (START_DATE_OFFSET_BEFORE, ugettext_noop("Before Date By")),
            (START_DATE_OFFSET_AFTER, ugettext_noop("After Date By")),
        )
    )
    start_day_of_week = forms.ChoiceField(
        required=False,
        choices=(
            (DAY_SUN, ugettext_noop("Sunday")),
            (DAY_MON, ugettext_noop("Monday")),
            (DAY_TUE, ugettext_noop("Tuesday")),
            (DAY_WED, ugettext_noop("Wednesday")),
            (DAY_THU, ugettext_noop("Thursday")),
            (DAY_FRI, ugettext_noop("Friday")),
            (DAY_SAT, ugettext_noop("Saturday")),
        )
    )
    # becomes start_offset
    start_date_offset = forms.IntegerField(
        required=False,
        initial=0,
    )

    # Fieldset: Recipient
    recipient = forms.ChoiceField(
        choices=(
            (RECIPIENT_CASE, ugettext_noop("Case")),
            (RECIPIENT_OWNER, ugettext_noop("Case Owner")),
            (RECIPIENT_USER, ugettext_noop("Last User Who Modified Case")),
            (RECIPIENT_USER_GROUP, ugettext_noop("Mobile Worker Group")),
            (RECIPIENT_ALL_SUBCASES, ugettext_noop("All Child Cases")),
            (RECIPIENT_SUBCASE, ugettext_noop("Specific Child Case")),
            (RECIPIENT_PARENT_CASE, ugettext_noop("Parent Case")),
        ),
    )
    ## recipient = RECIPIENT_SUBCASE
    recipient_case_match_property = forms.CharField(
        label=ugettext_noop("Enter a Case Property"),
        required=False
    )
    recipient_case_match_type = forms.ChoiceField(
        required=False,
        choices=MATCH_TYPE_CHOICES,
    )
    recipient_case_match_value = forms.CharField(
        label=ugettext_noop("Value"),
        required=False
    )
    ## recipient = RECIPIENT_USER_GROUP
    user_group_id = ChoiceField(
        required=False,
        label=ugettext_noop("Mobile Worker Group"),
    )

    # Fieldset: Message Content
    method = forms.ChoiceField(
        label=ugettext_noop("Send"),
        choices=(
            (METHOD_SMS, ugettext_noop("SMS")),
        ),
    )

    global_timeouts = forms.CharField(
        label=ugettext_noop("Timeouts"),
        required=False,
    )

    default_lang = forms.ChoiceField(
        required=False,
        label=ugettext_noop("Default Language"),
        choices=(
            ('en', ugettext_noop("English (en)")),
        )
    )

    event_timing = forms.ChoiceField(
        label=ugettext_noop("Time of Day"),
    )

    event_interpretation = forms.ChoiceField(
        label=ugettext_noop("Schedule Type"),
        initial=EVENT_AS_OFFSET,
        choices=EVENT_CHOICES,
        widget=forms.HiddenInput  # validate as choice, but don't show the widget.
    )

    # contains a string-ified JSON object of events
    events = forms.CharField(
        required=False,
        widget=forms.HiddenInput
    )

    # Fieldset: Repeat
    repeat_type = forms.ChoiceField(
        required=False,
        label=ugettext_noop("Repeat Reminder"),
        initial=REPEAT_TYPE_NO,
        choices=(
            (REPEAT_TYPE_NO, ugettext_noop("No")),  # reminder_type = ONE_TIME
            (REPEAT_TYPE_INDEFINITE, ugettext_noop("Indefinitely")),  # reminder_type = DEFAULT, max_iteration_count = -1
            (REPEAT_TYPE_SPECIFIC, ugettext_noop("Specific Number of Times")),
        )
    )
    # shown if repeat_type != 'no_repeat'
    schedule_length = forms.IntegerField(
        required=False,
        label=ugettext_noop("Repeat Every"),
    )
    # shown if repeat_type == 'specific' (0 if no_repeat, -1 if indefinite)
    max_iteration_count = forms.IntegerField(
        required=False,
        label=ugettext_noop("Number of Times"),
    )
    # shown if repeat_type != 'no_repeat'
    stop_condition = forms.ChoiceField(
        required=False,
        label="",
        choices=(
            ('', ugettext_noop('(none)')),
            (STOP_CONDITION_CASE_PROPERTY, ugettext_noop('Based on Case Property')),
        )
    )
    until = forms.CharField(
        required=False,
        label=ugettext_noop("Enter a Case Property"),
    )

    # Advanced Toggle
    submit_partial_forms = forms.BooleanField(
        required=False,
        label=ugettext_noop("Submit Partial Forms"),
    )
    include_case_side_effects = forms.BooleanField(
        required=False,
        label=ugettext_noop("Include Case Changes for Partial Forms"),
    )
    # only show if SMS_SURVEY or IVR_SURVEY is chosen
    max_question_retries = forms.ChoiceField(
        required=False,
        choices=((n, n) for n in QUESTION_RETRY_CHOICES)
    )

    force_surveys_to_use_triggered_case = forms.BooleanField(
        required=False,
        label=ugettext_noop("For Surveys, force answers to affect "
                              "case sending the survey."),
    )

    use_custom_content_handler = BooleanField(
        required=False,
        label=ugettext_noop("Use Custom Content Handler")
    )
    custom_content_handler = TrimmedCharField(
        required=False,
        label=ugettext_noop("Please Specify Custom Content Handler")
    )

    def __init__(self, data=None, is_previewer=False,
                 domain=None, is_edit=False, can_use_survey=False,
                 use_custom_content_handler=False,
                 custom_content_handler=None,
                 available_languages=None, *args, **kwargs
    ):
        available_languages = available_languages or ['en']
        self.available_languages = available_languages
        self.initial_event = {
            'day_num': 0,
            'fire_time_type': FIRE_TIME_DEFAULT,
            'subject': dict([(l, '') for l in available_languages]),
            'message': dict([(l, '') for l in available_languages]),
        }

        if 'initial' not in kwargs:
            kwargs['initial'] = {
                'event_timing': self._format_event_timing_choice(EVENT_AS_OFFSET,
                                                                 FIRE_TIME_DEFAULT, EVENT_TIMING_IMMEDIATE),
                'events': json.dumps([self.initial_event])
            }

        if is_edit:
            max_iteration_count = kwargs['initial']['max_iteration_count']
            if max_iteration_count == 1:
                repeat_type = REPEAT_TYPE_NO
            elif max_iteration_count == REPEAT_SCHEDULE_INDEFINITELY:
                repeat_type = REPEAT_TYPE_INDEFINITE
            else:
                repeat_type = REPEAT_TYPE_SPECIFIC
            kwargs['initial']['repeat_type'] = repeat_type

        super(BaseScheduleCaseReminderForm, self).__init__(data, *args, **kwargs)

        self.domain = domain
        self.is_edit = is_edit
        self.is_previewer = is_previewer

        self.fields['user_group_id'].choices = Group.choices_by_domain(self.domain)
        self.fields['default_lang'].choices = [(l, l) for l in available_languages]

        if can_use_survey:
            add_field_choices(self, 'method', [
                (METHOD_SMS_SURVEY, _('SMS Survey')),
            ])

        if is_previewer and can_use_survey:
            add_field_choices(self, 'method', [
                (METHOD_IVR_SURVEY, _('IVR Survey')),
                (METHOD_SMS_CALLBACK, _('SMS Expecting Callback')),
            ])

        if toggles.EMAIL_IN_REMINDERS.enabled(self.domain):
            add_field_choices(self, 'method', [
                (METHOD_EMAIL, _('Email')),
            ])

        from corehq.apps.reminders.views import RemindersListView
        self.helper = FormHelper()
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("Basic Information"),
                crispy.Field(
                    'nickname',
                    css_class='input-large',
                ),
            ),
            self.section_start,
            self.section_recipient,
            self.section_message,
            self.section_repeat,
            self.section_advanced,
            FormActions(
                StrictButton(
                    _("Update Reminder") if is_edit else _("Create Reminder"),
                    css_class='btn-primary',
                    type='submit',
                ),
                crispy.HTML('<a href="%s" class="btn">%s</a>' % (
                    reverse(RemindersListView.urlname, args=[self.domain]),
                    _("Cancel")
                )),
            )
        )

    @property
    def ui_type(self):
        raise NotImplementedError("You must specify a ui_type for the reminder")

    @property
    def section_start(self):
        return crispy.Fieldset(
            _('Start'),
            crispy.HTML(
                '<p style="padding: 0; margin-bottom: 1.5em;">'
                '<i class="icon-info-sign"></i> %s</p>' % _(
                    "Choose what will cause this reminder to be sent"
                ),
            ),
            *self.section_start_fields
        )

    @property
    def section_start_fields(self):
        return [
            FieldWithHelpBubble(
                'case_type',
                css_class="input-xlarge",
                data_bind="value: case_type, typeahead: available_case_types",
                placeholder=_("Enter a Case Type"),
                help_bubble_text=_(
                    "Choose which case type this reminder will be "
                    "sent out for."
                ),
            ),
            FieldWithHelpBubble(
                'start_reminder_on',
                data_bind="value: start_reminder_on",
                css_class="input-xlarge",
                help_bubble_text=("Reminders can either start based on a date in a case property "
                                  "or if the case is in a particular state (ex: case property 'high_risk' "
                                  "is equal to 'yes')")
            ),
            crispy.Div(
                BootstrapMultiField(
                    _("When Case Property"),
                    InlineField(
                        'start_property',
                        css_class="input-xlarge",
                        data_bind="typeahead: getAvailableCaseProperties",
                    ),
                    InlineField(
                        'start_match_type',
                        data_bind="value: start_match_type",
                    ),
                    InlineField(
                        'start_value',
                        style="margin-left: 5px;",
                        data_bind="visible: isStartMatchValueVisible",
                    ),
                ),
                data_bind="visible: isStartReminderCaseProperty",
            ),
            crispy.Div(
                BootstrapMultiField(
                    _("Day of Reminder"),
                    InlineField(
                        'start_property_offset_type',
                        data_bind="value: start_property_offset_type",
                        css_class="input-xlarge",
                    ),
                    InlineField(
                        'start_property_offset',
                        css_class='input-mini',
                        style="margin-left: 5px;",
                        data_bind="visible: isStartPropertyOffsetVisible",
                    ),
                    crispy.Div(
                        crispy.HTML('day(s)'),
                        css_class="help-inline",
                        data_bind="visible: isStartPropertyOffsetVisible",
                    ),
                    InlineField(
                        'start_day_of_week',
                        css_class='input-medium',
                        data_bind="visible: isStartDayOfWeekVisible",
                    ),
                ),
            ),
            crispy.Div(
                crispy.Field(
                    'start_date',
                    placeholder=_("Enter Case Property"),
                    css_class="input-xlarge",
                    data_bind="typeahead: getAvailableCaseProperties",
                ),
                BootstrapMultiField(
                    "",
                    InlineField(
                        'start_date_offset_type',
                        css_class="input-xlarge",
                    ),
                    crispy.Div(
                        InlineField(
                            'start_date_offset',
                            css_class='input-mini',

                        ),
                        crispy.HTML('<p class="help-inline">day(s)</p>'),
                        style='display: inline; margin-left: 5px;'
                    )
                ),
                data_bind="visible: isStartReminderCaseDate"
            ),
        ]

    @property
    def section_recipient(self):
        return crispy.Fieldset(
            _("Recipient"),
            FieldWithHelpBubble(
                'recipient',
                data_bind="value: recipient",
                help_bubble_text=("The contact related to the case that reminder should go to.  The Case "
                                  "Owners are any mobile workers for which the case appears on their phone. "
                                  "For cases with child or parent cases, you can also send the message to those "
                                  "contacts. "),
                css_class="input-xlarge",
            ),
            BootstrapMultiField(
                _("When Case Property"),
                InlineField(
                    'recipient_case_match_property',
                    css_class="input-xlarge",
                    data_bind="typeahead: getAvailableSubcaseProperties",
                ),
                InlineField(
                    'recipient_case_match_type',
                    data_bind="value: recipient_case_match_type",
                ),
                InlineField(
                    'recipient_case_match_value',
                    data_bind="visible: isRecipientCaseValueVisible",
                ),
                data_bind="visible: isRecipientSubcase",
            ),
            crispy.Div(
                crispy.Field(
                    'user_group_id',
                    css_class="input-xlarge",
                ),
                data_bind="visible: isRecipientGroup"
            ),
        )

    @property
    def section_message(self):
        return crispy.Fieldset(
            _("Message Content") if self.ui_type == UI_SIMPLE_FIXED else _("Schedule"),
            *self.section_message_fields
        )

    @property
    def section_message_fields(self):
        return [
            FieldWithHelpBubble(
                'method',
                data_bind="value: method",
                help_bubble_text=("Send a single SMS message or an interactive SMS survey. "
                                  "SMS surveys are designed in the Surveys or Application "
                                  "section. "),
                css_class="input-xlarge",
            ),
            crispy.Field('event_interpretation', data_bind="value: event_interpretation"),
            HiddenFieldWithErrors('events', data_bind="value: events"),
        ]

    @property
    def timing_fields(self):
        return [
            BootstrapMultiField(
                _("Time of Day"),
                InlineField(
                    'event_timing',
                    data_bind="value: event_timing",
                    css_class="input-xlarge",
                ),
                crispy.Div(
                    style="display: inline;",
                    data_bind="template: {name: 'event-fire-template', foreach: eventObjects}"
                ),
                css_id="timing_block",
                help_bubble_text=("This controls when the message will be sent. The Time in Case "
                                  "option is useful, for example, if the recipient has chosen a "
                                  "specific time to receive the message.")
            ),
            crispy.Div(
                style="display: inline;",
                data_bind="template: {name: 'event-general-template', foreach: eventObjects}"
            )
        ]

    @property
    def section_repeat(self):
        return crispy.Fieldset(
            _("Repeat"),
            crispy.Field(
                'repeat_type',
                data_bind="value: repeat_type",
                css_class="input-xlarge",
            ),
            crispy.Div(
                crispy.Field(
                    'max_iteration_count',
                    css_class="input-medium",
                ),
                data_bind="visible: isMaxIterationCountVisible",
            ),
            BootstrapMultiField(
                _("Repeat Every"),
                InlineField(
                    'schedule_length',
                    css_class="input-medium",
                ),
                crispy.HTML('<p class="help-inline">day(s)</p>'),
                data_bind="visible: isScheduleLengthVisible",
            ),
        )

    @property
    def section_advanced(self):
        fields = [
            BootstrapMultiField(
                _("Additional Stop Condition"),
                InlineField(
                    'stop_condition',
                    data_bind="value: stop_condition",
                    css_class="input-xlarge",
                ),
                crispy.Div(
                    InlineField(
                        'until',
                        css_class="input-large",
                        data_bind="typeahead: getAvailableCaseProperties",
                    ),
                    css_class="help-inline",
                    data_bind="visible: isUntilVisible",
                ),
                help_bubble_text=_("Reminders can be stopped after a date set in the case, or if a particular "
                                   "case property is set to OK.  Choose either a case property that is a date or "
                                   "a case property that is going to be set to OK.  Reminders will always stop if "
                                   "the start condition is no longer true or if the case that triggered the "
                                   "reminder is closed."),
                css_id="stop-condition-group",
            ),
            crispy.Div(
                BootstrapMultiField(
                    _("Default Language"),
                    InlineField(
                        'default_lang',
                        data_bind="options: available_languages, "
                                  "value: default_lang, "
                                  "optionsText: 'name', optionsValue: 'langcode'",
                        css_class="input-xlarge",
                    ),
                ),
                data_bind="visible: showDefaultLanguageOption",
            ),
            crispy.Div(
                FieldWithHelpBubble(
                    'global_timeouts',
                    data_bind="value: global_timeouts",
                    placeholder="e.g. 30,60,180",
                    help_bubble_text=_(
                        "Will repeat the last message or question if the "
                        "user does not respond.  Specify each interval "
                        "(in minutes) separated by a comma. "
                        "After the last interval, the survey will be closed. "
                    ),
                ),
                data_bind="visible: isGlobalTimeoutsVisible",
            ),
            crispy.Div(
                FieldWithHelpBubble(
                    'max_question_retries',
                    help_bubble_text=_("For IVR surveys, the number of times a person can provide an invalid "
                                       "answer before the call will hang up. ")
                ),
                data_bind="visible: isMaxQuestionRetriesVisible",
            ),
            crispy.Div(
                FieldWithHelpBubble(
                    'submit_partial_forms',
                    data_bind="checked: submit_partial_forms",
                    help_bubble_text=_(
                        "For surveys, this will let forms be saved even if "
                        "the survey has not been completed and the user is "
                        "not responding."
                    ),
                ),
                data_bind="visible: isPartialSubmissionsVisible",
            ),
            crispy.Div(
                FieldWithHelpBubble(
                    'include_case_side_effects',
                    help_bubble_text=_("When submitting a partial survey, this controls whether the corresponding "
                                       "case should be created, updated or closed.  This is may not be safe to do if "
                                       "the form has not been completed. ")
                ),
                data_bind="visible: isPartialSubmissionsVisible() && submit_partial_forms()",
            ),
            crispy.Div(
                'force_surveys_to_use_triggered_case',
                data_bind="visible: isForceSurveysToUsedTriggeredCaseVisible",
            ),
        ]
        if self.is_previewer:
            fields.append(
                BootstrapMultiField(
                    "",
                    InlineField(
                        'use_custom_content_handler',
                        data_bind="checked: use_custom_content_handler",
                    ),
                    InlineField(
                        'custom_content_handler',
                        css_class="input-xxlarge",
                        data_bind="visible: use_custom_content_handler",
                    ),
                )
            )

        return FieldsetAccordionGroup(
            _("Advanced Options"),
            *fields,
            active=False
        )

    @property
    def current_values(self):
        current_values = {}
        for field_name in self.fields.keys():
            current_values[field_name] = self[field_name].value()
        return current_values

    @property
    def relevant_choices(self):
        return {
            'MATCH_ANY_VALUE': MATCH_ANY_VALUE,
            'START_REMINDER_ON_CASE_PROPERTY': START_REMINDER_ON_CASE_PROPERTY,
            'START_REMINDER_ON_CASE_DATE': START_REMINDER_ON_CASE_DATE,
            'START_REMINDER_ON_DAY_OF_WEEK': START_REMINDER_ON_DAY_OF_WEEK,
            'RECIPIENT_CASE': RECIPIENT_CASE,
            'RECIPIENT_SUBCASE': RECIPIENT_SUBCASE,
            'RECIPIENT_USER_GROUP': RECIPIENT_USER_GROUP,
            'METHOD_SMS': METHOD_SMS,
            'METHOD_SMS_CALLBACK': METHOD_SMS_CALLBACK,
            'METHOD_SMS_SURVEY': METHOD_SMS_SURVEY,
            'METHOD_IVR_SURVEY': METHOD_IVR_SURVEY,
            'METHOD_EMAIL': METHOD_EMAIL,
            'START_PROPERTY_OFFSET_DELAY': START_PROPERTY_OFFSET_DELAY,
            'START_PROPERTY_OFFSET_IMMEDIATE': START_PROPERTY_OFFSET_IMMEDIATE,
            'FIRE_TIME_DEFAULT': FIRE_TIME_DEFAULT,
            'FIRE_TIME_CASE_PROPERTY': FIRE_TIME_CASE_PROPERTY,
            'FIRE_TIME_RANDOM': FIRE_TIME_RANDOM,
            'EVENT_AS_OFFSET': EVENT_AS_OFFSET,
            'EVENT_AS_SCHEDULE': EVENT_AS_SCHEDULE,
            'UI_SIMPLE_FIXED': UI_SIMPLE_FIXED,
            'UI_COMPLEX': UI_COMPLEX,
            'EVENT_TIMING_IMMEDIATE': EVENT_TIMING_IMMEDIATE,
            'REPEAT_TYPE_NO': REPEAT_TYPE_NO,
            'REPEAT_TYPE_INDEFINITE': REPEAT_TYPE_INDEFINITE,
            'REPEAT_TYPE_SPECIFIC': REPEAT_TYPE_SPECIFIC,
            'STOP_CONDITION_CASE_PROPERTY': STOP_CONDITION_CASE_PROPERTY,
        }

    @staticmethod
    def _format_event_timing_choice(event_interpretation, fire_time_type, special=None):
        return json.dumps({
            'event_interpretation': event_interpretation,
            'fire_time_type': fire_time_type,
            'special': special,
        })

    def clean_case_type(self):
        # todo check start_condition type when we get to the complex form
        case_property = self.cleaned_data['case_type'].strip()
        if not case_property:
            raise ValidationError(_("Please specify a case type."))
        return case_property

    def clean_default_lang(self):
        if len(self.available_languages) == 1:
            return self.available_languages[0]
        else:
            return self.cleaned_data["default_lang"]

    def clean_start_property(self):
        start_reminder_on = self.cleaned_data['start_reminder_on']
        if start_reminder_on == START_REMINDER_ON_CASE_PROPERTY:
            start_property = self.cleaned_data['start_property'].strip()
            if not start_property:
                raise ValidationError(_(
                    "Please enter a case property for the match criteria."
                ))
            return start_property
        if start_reminder_on == START_REMINDER_ALL_CASES:
            return START_PROPERTY_ALL_CASES_VALUE
        return None

    def clean_start_match_type(self):
        start_reminder_on = self.cleaned_data['start_reminder_on']
        if start_reminder_on == START_REMINDER_ON_CASE_PROPERTY:
            return self.cleaned_data['start_match_type']
        if start_reminder_on == START_REMINDER_ALL_CASES:
            return MATCH_ANY_VALUE
        return None

    def clean_start_value(self):
        if (self.cleaned_data['start_reminder_on'] == START_REMINDER_ON_CASE_PROPERTY
           and self.cleaned_data['start_match_type'] != MATCH_ANY_VALUE):
            start_value = self.cleaned_data['start_value'].strip()
            if not start_value:
                raise ValidationError(_(
                    "You must specify a value for the case property "
                    "match criteria."
                ))
            return start_value
        return None

    def clean_start_property_offset(self):
        if (self.cleaned_data['start_property_offset_type'] ==
            START_PROPERTY_OFFSET_IMMEDIATE):
            return 0
        elif (self.cleaned_data['start_property_offset_type'] ==
            START_PROPERTY_OFFSET_DELAY):
            start_property_offset = self.cleaned_data['start_property_offset']
            if start_property_offset < 0:
                raise ValidationError(_("Please enter a non-negative number."))
            return start_property_offset
        else:
            return None

    def clean_start_day_of_week(self):
        if self.cleaned_data['start_property_offset_type'] == START_REMINDER_ON_DAY_OF_WEEK:
            day_of_week = self.cleaned_data['start_day_of_week']
            try:
                day_of_week = int(day_of_week)
                assert day_of_week >= 0 and day_of_week <= 6
                return day_of_week
            except (ValueError, TypeError, AssertionError):
                raise ValidationError(_("Please choose a day of the week."))
        return DAY_ANY

    def clean_start_date(self):
        if (self.cleaned_data['start_property_offset_type'] ==
            START_REMINDER_ON_CASE_DATE):
            start_date = self.cleaned_data['start_date'].strip()
            if not start_date:
                raise ValidationError(_(
                    "You must specify a case property that will provide the "
                    "start date."
                ))
            return start_date
        return None

    def clean_start_date_offset(self):
        if (self.cleaned_data['start_property_offset_type'] ==
            START_REMINDER_ON_CASE_DATE):
            start_date_offset = self.cleaned_data['start_date_offset']
            if start_date_offset < 0:
                raise ValidationError("Please enter a positive number.")
            if self.cleaned_data['start_date_offset_type'] == START_DATE_OFFSET_BEFORE:
                return -start_date_offset
            return start_date_offset
        return None

    def clean_user_group_id(self):
        if self.cleaned_data['recipient'] == RECIPIENT_USER_GROUP:
            value = self.cleaned_data['user_group_id']
            return clean_group_id(value, self.domain)
        else:
            return None

    def clean_recipient_case_match_property(self):
        if self.cleaned_data['recipient'] == RECIPIENT_SUBCASE:
            case_property = self.cleaned_data['recipient_case_match_property'].strip()
            if not case_property:
                raise ValidationError(_(
                    "You must specify a case property for the case's "
                    "child case."
                ))
            return case_property
        if self.cleaned_data['recipient'] == RECIPIENT_ALL_SUBCASES:
            return '_id'
        return None

    def clean_recipient_case_match_type(self):
        if self.cleaned_data['recipient'] == RECIPIENT_SUBCASE:
            return self.cleaned_data['recipient_case_match_type']
        if self.cleaned_data['recipient'] == RECIPIENT_ALL_SUBCASES:
            return MATCH_ANY_VALUE
        return None

    def clean_recipient_case_match_value(self):
        if (self.cleaned_data['recipient'] == RECIPIENT_SUBCASE
           and self.cleaned_data['recipient_case_match_type'] != MATCH_ANY_VALUE):
            value = self.cleaned_data['recipient_case_match_value'].strip()
            if not value:
                raise ValidationError(_("You must provide a value."))
            return value
        return None

    def _clean_timeouts(self, value):
        if value:
            timeouts_str = value.split(",")
            timeouts_int = []
            for t in timeouts_str:
                try:
                    t = int(t.strip())
                    assert t > 0
                    timeouts_int.append(t)
                except (ValueError, AssertionError):
                    raise ValidationError(_(
                        "Timeout intervals must be a list of positive "
                        "numbers separated by commas."
                    ))
            return timeouts_int
        return []

    def clean_global_timeouts(self):
        method = self.cleaned_data['method']
        if (self.ui_type == UI_SIMPLE_FIXED and
            method in (METHOD_SMS_CALLBACK, METHOD_SMS_SURVEY, METHOD_IVR_SURVEY)):
            return self._clean_timeouts(self.cleaned_data['global_timeouts'])
        else:
            return []

    def clean_translated_field(self, translations, default_lang):
        for lang, msg in translations.items():
            if msg:
                msg = msg.strip()
            if not msg:
                del translations[lang]
            else:
                translations[lang] = msg
        if default_lang not in translations:
            default_lang_name = (get_language_name(default_lang) or
                default_lang)
            raise ValidationError(_("Please provide messages for the "
                "default language (%(language)s) or change the default "
                "language at the bottom of the page.") %
                {"language": default_lang_name})
        return translations

    def clean_events(self):
        method = self.cleaned_data['method']
        try:
            events = json.loads(self.cleaned_data['events'])
        except ValueError:
            raise ValidationError(_(
                "A valid JSON object was not passed in the events input."
            ))

        default_lang = self.cleaned_data["default_lang"]
        has_fire_time_case_property = False
        for event in events:
            eventForm = CaseReminderEventForm(
                data=event,
            )
            if not eventForm.is_valid():
                raise ValidationError(_(
                    "Your event form didn't turn out quite right."
                ))

            event.update(eventForm.cleaned_data)

            # the reason why we clean the following fields here instead of eventForm is so that
            # we can utilize the ValidationErrors for this field.

            # clean subject:
            if method == METHOD_EMAIL:
                event['subject'] = self.clean_translated_field(
                    event.get('subject', {}), default_lang)
            else:
                event['subject'] = {}

            # clean message:
            if method in (METHOD_SMS, METHOD_SMS_CALLBACK, METHOD_EMAIL):
                event['message'] = self.clean_translated_field(
                    event.get('message', {}), default_lang)
            else:
                event['message'] = {}

            # clean form_unique_id:
            if method in (METHOD_SMS, METHOD_SMS_CALLBACK, METHOD_EMAIL):
                event['form_unique_id'] = None
            else:
                form_unique_id = event.get('form_unique_id')
                if not form_unique_id:
                    raise ValidationError(_(
                        "Please create a form for the survey first, "
                        "and then create the reminder."
                    ))
                validate_form_unique_id(form_unique_id, self.domain)

            fire_time_type = event['fire_time_type']

            # clean fire_time:
            if fire_time_type == FIRE_TIME_CASE_PROPERTY:
                event['fire_time'] = None
                has_fire_time_case_property = True
            elif event['is_immediate']:
                event['fire_time'] = ONE_MINUTE_OFFSET
            else:
                event['fire_time'] = validate_time(event['fire_time'])

            # clean fire_time_aux:
            if fire_time_type != FIRE_TIME_CASE_PROPERTY:
                event['fire_time_aux'] = None
            elif not event.get('fire_time_aux'):
                raise ValidationError(_(
                    "Please enter the case property from which to pull "
                    "the time."
                ))

            # clean time_window_length:
            time_window_length = event['time_window_length']
            if fire_time_type != FIRE_TIME_RANDOM:
                event['time_window_length'] = None
            elif not (0 < time_window_length < 1440):
                raise ValidationError(_(
                    "Window Length must be greater than 0 and less "
                    "than 1440 minutes."
                ))

            # clean day_num:
            if self.ui_type == UI_SIMPLE_FIXED or event['is_immediate']:
                event['day_num'] = 0
            else:
                event['day_num'] = validate_integer(event['day_num'],
                    _('Day must be specified and must be a non-negative number.'),
                    nonnegative=True)

            # clean callback_timeout_intervals:
            if (method == METHOD_SMS_CALLBACK
                or method == METHOD_IVR_SURVEY
                or method == METHOD_SMS_SURVEY):
                if self.ui_type == UI_SIMPLE_FIXED:
                    value = self.cleaned_data.get('global_timeouts', [])
                else:
                    value = self._clean_timeouts(event["callback_timeout_intervals"])
                event['callback_timeout_intervals'] = value
            else:
                event['callback_timeout_intervals'] = []

            # delete all data that was just UI based:
            del event['message_data']  # this is only for storing the stringified version of message
            del event['subject_data']
            del event['is_immediate']

        event_interpretation = self.cleaned_data["event_interpretation"]
        if (event_interpretation == EVENT_AS_SCHEDULE and
            not has_fire_time_case_property):
            event_time = lambda e: (
                (1440 * e['day_num']) +
                (60 * e['fire_time'].hour) +
                e['fire_time'].minute)
            events.sort(key=event_time)

        return events

    def get_min_schedule_length(self):
        """
        Only meant to be called when the event_interpretation is
        EVENT_AS_SCHEDULE. This will return the minimum allowed value for
        schedule_length.
        """
        max_day_num = 0
        for event in self.cleaned_data.get("events", []):
            day_num = event['day_num']
            if day_num > max_day_num:
                max_day_num = day_num
        return max_day_num + 1

    def clean_schedule_length(self):
        event_interpretation = self.cleaned_data["event_interpretation"]
        if self.cleaned_data['repeat_type'] == REPEAT_TYPE_NO:
            if event_interpretation == EVENT_AS_SCHEDULE:
                return self.get_min_schedule_length()
            else:
                return 1
        value = self.cleaned_data['schedule_length']
        if event_interpretation == EVENT_AS_OFFSET and value < 0:
            raise ValidationError("Please enter a non-negative number.")
        elif event_interpretation == EVENT_AS_SCHEDULE:
            min_value = self.get_min_schedule_length()
            if value < min_value:
                raise ValidationError("This must be at least %s based on the "
                    "schedule defined above." % min_value)
        return value

    def clean_max_iteration_count(self):
        repeat_type = self.cleaned_data['repeat_type']
        if repeat_type == REPEAT_TYPE_NO:
            return 1
        if repeat_type == REPEAT_TYPE_INDEFINITE:
            return REPEAT_SCHEDULE_INDEFINITELY
        max_iteration_count = self.cleaned_data['max_iteration_count']
        if max_iteration_count <= 0:
            raise ValidationError(_(
                "Please enter a number that is 1 or greater."
            ))
        return max_iteration_count

    def clean_until(self):
        if self.cleaned_data['stop_condition'] == STOP_CONDITION_CASE_PROPERTY:
            value = self.cleaned_data['until'].strip()
            if not value:
                raise ValidationError(_(
                    "You must specify a case property for the stop condition."
                ))
            return value
        return None

    def clean_max_question_retries(self):
        value = self.cleaned_data['max_question_retries']
        try:
            value = int(value)
        except ValueError:
            raise ValidationError(_(
                "Max question retries must be an integer."
            ))
        return value

    def clean_use_custom_content_handler(self):
        if self.is_previewer:
            return self.cleaned_data["use_custom_content_handler"]
        else:
            return None

    def clean_custom_content_handler(self):
        if self.is_previewer:
            value = self.cleaned_data["custom_content_handler"]
            if self.cleaned_data["use_custom_content_handler"]:
                if value in settings.ALLOWED_CUSTOM_CONTENT_HANDLERS:
                    return value
                else:
                    raise ValidationError(_("Invalid custom content handler."))
            else:
                return None
        else:
            return None

    def save(self, reminder_handler):
        if not isinstance(reminder_handler, CaseReminderHandler):
            raise ValueError(_(
                "You must save to a CaseReminderHandler object!"
            ))

        events = self.cleaned_data['events']
        event_objects = []
        for event in events:
            new_event = CaseReminderEvent()
            for prop, val in event.items():
                setattr(new_event, prop, val)
            event_objects.append(new_event)
        reminder_handler.events = event_objects

        fields = [
            'nickname',
            'case_type',
            'start_property',
            'start_match_type',
            'start_value',
            'start_date',
            'start_day_of_week',
            'recipient',
            'user_group_id',
            'recipient_case_match_property',
            'recipient_case_match_type',
            'recipient_case_match_value',
            'method',
            'event_interpretation',
            'schedule_length',
            'max_iteration_count',
            'until',
            'submit_partial_forms',
            'include_case_side_effects',
            'default_lang',
            'max_question_retries',
            'force_surveys_to_use_triggered_case',
        ]
        if self.is_previewer:
            fields.append('custom_content_handler')
        for field in fields:
            value = self.cleaned_data[field]
            if field == 'recipient' and value == RECIPIENT_ALL_SUBCASES:
                value = RECIPIENT_SUBCASE
            setattr(reminder_handler, field, value)

        start_property_offset = self.cleaned_data['start_property_offset']
        start_date_offset = self.cleaned_data['start_date_offset']
        reminder_handler.start_offset = (start_property_offset or
                                         start_date_offset or 0)
        reminder_handler.ui_type = self.ui_type
        reminder_handler.domain = self.domain
        reminder_handler.start_condition_type = CASE_CRITERIA

        # If any of the scheduling information has changed, have it recalculate
        # the schedule for each reminder instance
        if reminder_handler._id:
            old_definition = CaseReminderHandler.get(reminder_handler._id)
            save_kwargs = {
                "schedule_changed": reminder_handler.schedule_has_changed(old_definition),
                "prev_definition": old_definition,
            }
        else:
            save_kwargs = {}

        reminder_handler.save(**save_kwargs)

    @classmethod
    def compute_initial(cls, reminder_handler, available_languages):
        initial = {}
        fields = cls.__dict__['base_fields'].keys()
        for field in fields:
            try:
                current_val = getattr(reminder_handler, field, Ellipsis)
                if field == 'events':
                    events_json = []
                    for event in current_val:
                        event_json = event.to_json()

                        if not event_json.get("message", None):
                            event_json["message"] = {}

                        if not event_json.get("subject", None):
                            event_json["subject"] = {}

                        for langcode in available_languages:
                            if langcode not in event_json["message"]:
                                event_json["message"][langcode] = ""
                            if langcode not in event_json["subject"]:
                                event_json["subject"][langcode] = ""

                        timeouts = [str(i) for i in
                            event_json["callback_timeout_intervals"]]
                        event_json["callback_timeout_intervals"] = ", ".join(
                            timeouts)

                        events_json.append(event_json)
                    current_val = json.dumps(events_json)
                if (field == 'recipient'
                    and reminder_handler.recipient_case_match_property == '_id'
                    and reminder_handler.recipient_case_match_type == MATCH_ANY_VALUE
                ):
                    current_val = RECIPIENT_ALL_SUBCASES
                if current_val is not Ellipsis:
                    initial[field] = current_val
                if field is 'custom_content_handler' and current_val is not None:
                    initial['use_custom_content_handler'] = True
            except AttributeError:
                pass

        if (initial['start_property'] == START_PROPERTY_ALL_CASES_VALUE
            and initial['start_match_type'] == MATCH_ANY_VALUE):
            initial['start_reminder_on'] = START_REMINDER_ALL_CASES
            del initial['start_property']
            del initial['start_match_type']
        else:
            initial['start_reminder_on'] = START_REMINDER_ON_CASE_PROPERTY

        if reminder_handler.start_date is None:
            initial['start_property_offset_type'] = (
                START_PROPERTY_OFFSET_IMMEDIATE
                if reminder_handler.start_offset == 0
                else START_PROPERTY_OFFSET_DELAY)
            initial['start_property_offset'] = reminder_handler.start_offset
        else:
            initial['start_property_offset_type'] = START_REMINDER_ON_CASE_DATE
            initial['start_date_offset_type'] = (
                START_DATE_OFFSET_BEFORE
                if reminder_handler.start_offset < 0
                else START_DATE_OFFSET_AFTER)
            initial['start_date_offset'] = abs(reminder_handler.start_offset)

        if reminder_handler.start_day_of_week != DAY_ANY:
            initial['start_property_offset_type'] = START_REMINDER_ON_DAY_OF_WEEK

        if (len(reminder_handler.events) == 1 and
            reminder_handler.event_interpretation == EVENT_AS_OFFSET and
            reminder_handler.events[0].day_num == 0 and
            reminder_handler.events[0].fire_time == ONE_MINUTE_OFFSET):
            sends_immediately = True
        else:
            sends_immediately = False

        if len(reminder_handler.events) > 0:
            initial['event_timing'] = cls._format_event_timing_choice(
                reminder_handler.event_interpretation,
                reminder_handler.events[0].fire_time_type,
                (EVENT_TIMING_IMMEDIATE if sends_immediately and
                 reminder_handler.ui_type == UI_SIMPLE_FIXED else None),
            )

        if reminder_handler.until:
            initial['stop_condition'] = STOP_CONDITION_CASE_PROPERTY

        return initial


class SimpleScheduleCaseReminderForm(BaseScheduleCaseReminderForm):

    def __init__(self, *args, **kwargs):
        super(SimpleScheduleCaseReminderForm, self).__init__(*args, **kwargs)

        event_timing_choices = (
            ((EVENT_AS_OFFSET, FIRE_TIME_DEFAULT, EVENT_TIMING_IMMEDIATE),
             _("Immediately When Triggered")),
            ((EVENT_AS_SCHEDULE, FIRE_TIME_DEFAULT, None),
             _("At a Specific Time")),
            ((EVENT_AS_OFFSET, FIRE_TIME_DEFAULT, None),
             _("Delay After Start")),
            ((EVENT_AS_SCHEDULE, FIRE_TIME_CASE_PROPERTY, None),
             _("Time Specific in Case")),
            ((EVENT_AS_SCHEDULE, FIRE_TIME_RANDOM, None),
             _("Random Time in Window")),
        )
        event_timing_choices = [(self._format_event_timing_choice(e[0][0], e[0][1], e[0][2]), e[1])
                                for e in event_timing_choices]
        self.fields['event_timing'].choices = event_timing_choices

    @property
    def ui_type(self):
        return UI_SIMPLE_FIXED

    @property
    def section_start_fields(self):
        start_fields = super(SimpleScheduleCaseReminderForm, self).section_start_fields
        start_fields.extend(self.timing_fields)
        return start_fields

    @property
    def section_message_fields(self):
        message_fields = super(SimpleScheduleCaseReminderForm, self).section_message_fields
        message_fields.append(
            crispy.Div(data_bind="template: {name: 'event-template', foreach: eventObjects}")
        )
        return message_fields

    @property
    def timing_fields(self):
        return [
            BootstrapMultiField(
                _("Time of Day"),
                InlineField(
                    'event_timing',
                    data_bind="value: event_timing",
                    css_class="input-xlarge",
                ),
                crispy.Div(
                    style="display: inline;",
                    data_bind="template: {name: 'event-fire-template', foreach: eventObjects}"
                ),
                css_id="timing_block",
                help_bubble_text=_("This controls when the message will be sent. The Time in Case "
                                   "option is useful, for example, if the recipient has chosen a "
                                   "specific time to receive the message.")
            ),
            crispy.Div(
                style="display: inline;",
                data_bind="template: {name: 'event-general-template', foreach: eventObjects}"
            )
        ]


class ComplexScheduleCaseReminderForm(BaseScheduleCaseReminderForm):

    def __init__(self, *args, **kwargs):
        super(ComplexScheduleCaseReminderForm, self).__init__(*args, **kwargs)

        event_timing_choices = (
            ((EVENT_AS_SCHEDULE, FIRE_TIME_DEFAULT, None),
             _("At a Specific Time")),
            ((EVENT_AS_OFFSET, FIRE_TIME_DEFAULT, None),
             _("Delay After Start By")),
            ((EVENT_AS_SCHEDULE, FIRE_TIME_CASE_PROPERTY, None),
             _("Time Specific in Case")
            ),
            ((EVENT_AS_SCHEDULE, FIRE_TIME_RANDOM, None),
             _("Random Time in Window")),
        )
        event_timing_choices = [(self._format_event_timing_choice(e[0][0], e[0][1], e[0][2]), e[1])
                                for e in event_timing_choices]
        self.fields['event_timing'].choices = event_timing_choices

    @property
    def ui_type(self):
        return UI_COMPLEX

    @property
    def section_message_fields(self):
        fields = super(ComplexScheduleCaseReminderForm, self).section_message_fields
        fields = fields[:1] + self.timing_fields + fields[1:]
        fields.append(crispy.Div(template='reminders/partial/complex_message_table.html'))
        return fields

    @property
    def timing_fields(self):
        return [
            BootstrapMultiField(
                _("Time of Day"),
                InlineField(
                    'event_timing',
                    data_bind="value: event_timing",
                    css_class="input-xlarge",
                ),
                css_id="timing_block",
                help_bubble_text=_("This controls when the message will be sent. The Time in Case "
                                   "option is useful, for example, if the recipient has chosen a "
                                   "specific time to receive the message.")
            ),
        ]


class CaseReminderEventForm(forms.Form):
    """
    This form creates or modifies a CaseReminderEvent.
    """
    fire_time_type = forms.ChoiceField(
        choices=(
            (FIRE_TIME_DEFAULT, ugettext_noop("Default")),
            (FIRE_TIME_CASE_PROPERTY, ugettext_noop("Case Property")),  # not valid when method != EVENT_AS_SCHEDULE
            (FIRE_TIME_RANDOM, ugettext_noop("Random")),  # not valid when method != EVENT_AS_SCHEDULE
        ),
        widget=forms.HiddenInput,  # don't actually display this widget to the user for now, but validate as choice
    )

    # EVENT_AS_OFFSET: number of days after last fire
    # EVENT_AS_SCHEDULE: number of days since the current event cycle began
    day_num = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput,
    )

    # EVENT_AS_OFFSET: number of HH:MM:SS after last fire
    # EVENT_AS_SCHEDULE: time of day
    fire_time = forms.TimeField(
        required=False,
        label=ugettext_noop("HH:MM:SS"),
    )

    # method must be EVENT_AS_SCHEDULE
    fire_time_aux = forms.CharField(
        required=False,
        label=ugettext_noop("Enter a Case Property"),
    )

    time_window_length = forms.IntegerField(
        label=ugettext_noop("Window Length (minutes)"),
        required=False
    )

    # subject is visible when the method of the reminder is METHOD_EMAIL
    # value will be a dict of {langcode: message}
    subject_data = forms.CharField(
        required=False,
        widget=forms.HiddenInput,
    )

    # message is visible when the method of the reminder is (METHOD_SMS, METHOD_SMS_CALLBACK, METHOD_EMAIL)
    # value will be a dict of {langcode: message}
    message_data = forms.CharField(
        required=False,
        widget=forms.HiddenInput,
    )

    # form_unique_id is visible when the method of the reminder is SMS_SURVEY or IVR_SURVEY
    form_unique_id = forms.CharField(
        required=False,
        label=ugettext_noop("Survey"),
    )

    callback_timeout_intervals = forms.CharField(
        required=False,
    )

    def __init__(self, ui_type=None, *args, **kwargs):
        super(CaseReminderEventForm, self).__init__(*args, **kwargs)

        self.ui_type = ui_type

        self.helper_fire_time = FormHelper()
        self.helper_fire_time.form_tag = False
        self.helper_fire_time.layout = crispy.Layout(
            crispy.Div(
                template="reminders/partial/fire_time_field.html",
            ),
            crispy.Div(
                InlineField(
                    'fire_time_aux',
                    data_bind="value: fire_time_aux, attr: {id: ''}",
                    css_class="input-large",
                ),
                css_class="help-inline",
                data_bind="visible: isFireTimeAuxVisible",
            ),
        )

        # Note the following is only used for the Simple UI.
        # The Complex UI goes off the template: reminders/partial/complex_message_table.html
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = crispy.Layout(
            crispy.Field('subject_data', data_bind="value: subject_data, attr: {id: ''}"),
            crispy.Field('message_data', data_bind="value: message_data, attr: {id: ''}"),
            crispy.Div(data_bind="template: {name: 'event-message-template', foreach: messageTranslations}, "
                                 "visible: isMessageVisible"),
            crispy.Div(
                crispy.Field(
                    'form_unique_id',
                    data_bind="value: form_unique_id, attr: {id: ''}",
                    css_class="input-xxlarge",
                ),
                data_bind="visible: isSurveyVisible",
            ),
        )

        self.helper_general = FormHelper()
        self.helper_general.form_tag = False
        self.helper_general.layout = crispy.Layout(
            crispy.Div(
                crispy.Field('time_window_length', data_bind="value: time_window_length, attr: {id: ''}"),
                data_bind="visible: isWindowLengthVisible",
            ),
            crispy.Field('fire_time_type', data_bind="value: fire_time_type, attr: {id: ''}"),
            crispy.Field('day_num', data_bind="value: day_num, attr: {id: ''}"),
        )


class CaseReminderEventMessageForm(forms.Form):
    """
    This form specifies the UI for messages in CaseReminderEventForm.
    """
    langcode = forms.CharField(
        required=False,
        widget=forms.HiddenInput
    )
    subject = forms.CharField(
        required=False,
        widget=forms.Textarea
    )
    message = forms.CharField(
        required=False,
        widget=forms.Textarea
    )

    def __init__(self, *args, **kwargs):
        super(CaseReminderEventMessageForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = crispy.Layout(
            crispy.Field('langcode', data_bind="value: langcode"),
            BootstrapMultiField(
                '%s <span data-bind="visible: languageLabel()">'
                '(<span data-bind="text:languageLabel"></span>)</span>' %
                _("Message"),
                InlineField(
                    'subject',
                    data_bind="value: subject, valueUpdate: 'keyup',"
                              "visible: $parent.isEmailSelected()",
                    css_class="input-xlarge",
                    rows="2",
                ),
                InlineField(
                    'message',
                    data_bind="value: message, valueUpdate: 'keyup'",
                    css_class="input-xlarge",
                    rows="2",
                ),
                crispy.Div(
                    style="padding-top: 10px; padding-left: 5px;",
                    data_bind="template: { name: 'event-message-length-template' },"
                              "visible: !$parent.isEmailSelected()"
                )
            ),
        )


def clean_selection(value):
    if value == "" or value is None:
        raise ValidationError(_("Please make a selection."))
    else:
        return value


class OneTimeReminderForm(Form):
    _cchq_domain = None
    send_type = ChoiceField(choices=NOW_OR_LATER)
    date = CharField(required=False)
    time = CharField(required=False)
    datetime = DateTimeField(required=False)
    recipient_type = ChoiceField(choices=ONE_TIME_RECIPIENT_CHOICES)
    case_group_id = CharField(required=False)
    user_group_id = CharField(required=False)
    content_type = ChoiceField(choices=(
        (METHOD_SMS, ugettext_lazy("SMS Message")),
    ))
    subject = TrimmedCharField(required=False)
    message = TrimmedCharField(required=False)
    form_unique_id = CharField(required=False)

    def __init__(self, *args, **kwargs):
        can_use_survey = kwargs.pop('can_use_survey', False)
        can_use_email = kwargs.pop('can_use_email', False)
        super(OneTimeReminderForm, self).__init__(*args, **kwargs)
        if can_use_survey:
            add_field_choices(self, 'content_type', [
                (METHOD_SMS_SURVEY, _('SMS Survey')),
            ])
        if can_use_email:
            add_field_choices(self, 'content_type', [
                (METHOD_EMAIL, _('Email')),
            ])

    def clean_recipient_type(self):
        return clean_selection(self.cleaned_data.get("recipient_type"))

    def clean_case_group_id(self):
        if self.cleaned_data.get("recipient_type") == RECIPIENT_SURVEY_SAMPLE:
            value = self.cleaned_data.get("case_group_id")
            return clean_case_group_id(value, self._cchq_domain)
        else:
            return None

    def clean_user_group_id(self):
        if self.cleaned_data.get("recipient_type") == RECIPIENT_USER_GROUP:
            value = self.cleaned_data.get("user_group_id")
            return clean_group_id(value, self._cchq_domain)
        else:
            return None

    def clean_date(self):
        if self.cleaned_data.get("send_type") == SEND_NOW:
            return None
        else:
            value = self.cleaned_data.get("date")
            validate_date(value)
            return parse(value).date()

    def clean_time(self):
        if self.cleaned_data.get("send_type") == SEND_NOW:
            return None
        else:
            value = self.cleaned_data.get("time")
            validate_time(value)
            return parse(value).time()

    def clean_subject(self):
        value = self.cleaned_data.get("subject")
        if self.cleaned_data.get("content_type") == METHOD_EMAIL:
            if value:
                return value
            else:
                raise ValidationError("This field is required.")
        else:
            return None

    def clean_message(self):
        value = self.cleaned_data.get("message")
        if self.cleaned_data.get("content_type") in (METHOD_SMS, METHOD_EMAIL):
            if value:
                return value
            else:
                raise ValidationError("This field is required.")
        else:
            return None

    def clean_datetime(self):
        utcnow = datetime.utcnow()
        timezone = get_timezone_for_user(None, self._cchq_domain) # Use project timezone only
        if self.cleaned_data.get("send_type") == SEND_NOW:
            start_datetime = utcnow + timedelta(minutes=1)
        else:
            dt = self.cleaned_data.get("date")
            tm = self.cleaned_data.get("time")
            if dt is None or tm is None:
                return None
            start_datetime = datetime.combine(dt, tm)
            start_datetime = UserTime(start_datetime, timezone).server_time().done()
            if start_datetime < utcnow:
                raise ValidationError(_("Date and time cannot occur in the past."))
        return start_datetime

    def clean_form_unique_id(self):
        if self.cleaned_data.get("content_type") == METHOD_SMS_SURVEY:
            value = self.cleaned_data.get("form_unique_id")
            if value is None:
                raise ValidationError(_("Please create a form first, and then create the broadcast."))
            validate_form_unique_id(value, self._cchq_domain)
            return value
        else:
            return None

class RecordListWidget(Widget):
    
    # When initialized, expects to be passed attrs={"input_name" : < first dot-separated name of all related records in the html form >}
    
    def value_from_datadict(self, data, files, name, *args, **kwargs):
        input_name = self.attrs["input_name"]
        raw = {}
        for key in data:
            if key.startswith(input_name + "."):
                raw[key] = data[key]
        
        data_dict = DotExpandedDict(raw)
        data_list = []
        if len(data_dict) > 0:
            for key in sorted(data_dict[input_name].iterkeys()):
                data_list.append(data_dict[input_name][key])
        
        return data_list

    def render(self, name, value, attrs=None):
        return render_to_string('reminders/partial/record_list_widget.html', {
            'value': value,
            'name': name,
        })

class RecordListField(Field):
    required = None
    label = None
    initial = None
    widget = None
    help_text = None
    
    # When initialized, expects to be passed kwarg input_name, which is the first dot-separated name of all related records in the html form

    def __init__(self, *args, **kwargs):
        input_name = kwargs.pop('input_name')
        kwargs['widget'] = RecordListWidget(attrs={"input_name" : input_name})
        super(RecordListField, self).__init__(*args, **kwargs)

    def clean(self, value):
        return value

class SurveyForm(Form):
    name = CharField()
    waves = RecordListField(input_name="wave")
    followups = RecordListField(input_name="followup")
    samples = RecordListField(input_name="sample")
    send_automatically = BooleanField(required=False)
    send_followup = BooleanField(required=False)
    
    def clean_waves(self):
        value = self.cleaned_data["waves"]
        datetimes = {}
        samples = [CommCareCaseGroup.get(sample["sample_id"]) for sample in self.cleaned_data.get("samples",[])]
        utcnow = datetime.utcnow()
        followups = [int(followup["interval"]) for followup in self.cleaned_data.get("followups", [])]
        followup_duration = sum(followups)
        start_end_intervals = []
        for wave_json in value:
            validate_date(wave_json["date"])
            validate_date(wave_json["end_date"])
            validate_time(wave_json["time"])
            
            # Convert the datetime to a string and compare it against the other datetimes
            # to make sure no two waves have the same start timestamp
            date = parse(wave_json["date"]).date()
            time = parse(wave_json["time"]).time()
            d8time = datetime.combine(date, time)
            datetime_string = string_to_datetime(d8time)
            if datetimes.get(datetime_string, False):
                raise ValidationError("Two waves cannot be scheduled at the same date and time.")
            datetimes[datetime_string] = True
            
            # Validate end date
            end_date = parse(wave_json["end_date"]).date()
            end_datetime = datetime.combine(end_date, time)
            days_between = (end_date - date).days
            if days_between < 1:
                raise ValidationError("End date must come after start date.")
            if days_between <= followup_duration:
                raise ValidationError("End date must come after all followups.")
            
            start_end_intervals.append((d8time, end_datetime))
            
            if wave_json["form_id"] == "--choose--":
                raise ValidationError("Please choose a questionnaire.")
            
            # If the wave was editable, make sure it is not being scheduled in the past for any sample
            if "ignore" not in wave_json:
                for sample in samples:
                    if CaseReminderHandler.timestamp_to_utc(sample, d8time) < utcnow:
                        raise ValidationError("Waves cannot be scheduled in the past.")
        
        # Ensure wave start and end dates do not overlap
        start_end_intervals.sort(key = lambda t : t[0])
        i = 0
        last_end = None
        for start_end in start_end_intervals:
            if i > 0 and (start_end[0] - last_end).days < 1:
                raise ValidationError("Waves must be scheduled at least one day apart.")
            i += 1
            last_end = start_end[1]
        
        return value
    
    def clean_followups(self):
        send_followup = self.cleaned_data["send_followup"]
        if send_followup:
            value = self.cleaned_data["followups"]
            for followup in value:
                try:
                    interval = int(followup["interval"])
                    assert interval > 0
                except (ValueError, AssertionError):
                    raise ValidationError("Follow-up intervals must be positive integers.")
                
            return value
        else:
            return []
    
    def clean_samples(self):
        value = self.cleaned_data["samples"]
        for sample_json in value:
            if sample_json["sample_id"] == "--choose--":
                raise ValidationError("Please choose a sample.")
            if sample_json.get("cati_operator", None) is None and sample_json["method"] == "CATI":
                raise ValidationError("Please create a mobile worker to use as a CATI Operator.")
        return value

    def clean(self):
        cleaned_data = super(SurveyForm, self).clean()
        return cleaned_data


class SurveySampleForm(Form):
    name = CharField()
    sample_contacts = RecordListField(input_name="sample_contact")
    time_zone = TimeZoneChoiceField()
    use_contact_upload_file = ChoiceField(choices=YES_OR_NO)
    contact_upload_file = FileField(required=False)
    
    def clean_sample_contacts(self):
        value = self.cleaned_data["sample_contacts"]
        if self.cleaned_data.get("use_contact_upload_file", "N") == "N":
            if len(value) == 0:
                raise ValidationError("Please add at least one contact.")
            for contact in value:
                contact["phone_number"] = validate_phone_number(contact["phone_number"])
        return value
    
    def clean_contact_upload_file(self):
        value = self.cleaned_data.get("contact_upload_file", None)
        if self.cleaned_data.get("use_contact_upload_file", "N") == "Y":
            if value is None:
                raise ValidationError("Please choose a file.")
            
            try:
                workbook = WorkbookJSONReader(value)
            except InvalidFileException:
                raise ValidationError("Invalid format. Please convert to Excel 2007 or higher (.xlsx) and try again.")
            
            try:
                worksheet = workbook.get_worksheet()
            except WorksheetNotFound:
                raise ValidationError("Workbook has no worksheets.")
            
            contacts = []
            for row in worksheet:
                if "PhoneNumber" not in row:
                    raise ValidationError("Column 'PhoneNumber' not found.")
                contacts.append({"phone_number" : validate_phone_number(row.get("PhoneNumber"))})
            
            if len(contacts) == 0:
                raise ValidationError(_("Please add at least one contact."))
            
            return contacts
        else:
            return None

class EditContactForm(Form):
    phone_number = CharField()
    
    def clean_phone_number(self):
        value = self.cleaned_data.get("phone_number")
        return validate_phone_number(value)

class ListField(Field):
    
    def __init__(self, *args, **kwargs):
        kwargs["widget"] = CheckboxSelectMultiple
        super(ListField, self).__init__(*args, **kwargs)
    
    def clean(self, value):
        return value

class RemindersInErrorForm(Form):
    selected_reminders = ListField(required=False)


class KeywordForm(Form):
    _cchq_domain = None
    _sk_id = None
    keyword = CharField(label=ugettext_noop("Keyword"))
    description = TrimmedCharField(label=ugettext_noop("Description"))
    override_open_sessions = BooleanField(
        required=False,
        initial=False,
        label=ugettext_noop("Override open SMS Surveys"),
    )
    allow_keyword_use_by = ChoiceField(
        required=False,
        label=ugettext_noop("Allow Keyword Use By"),
        initial='any',
        choices=(
            ('any', ugettext_noop("Both Mobile Workers and Cases")),
            ('users', ugettext_noop("Mobile Workers Only")),
            ('cases', ugettext_noop("Cases Only")),
        )
    )
    sender_content_type = ChoiceField(
        label=ugettext_noop("Send to Sender"),
    )
    sender_message = TrimmedCharField(
        required=False,
        label=ugettext_noop("Message"),
    )
    sender_form_unique_id = ChoiceField(
        required=False,
        label=ugettext_noop("Survey"),
    )
    other_recipient_content_type = ChoiceField(
        required=False,
        label=ugettext_noop("Notify Another Person"),
        initial=NO_RESPONSE,
    )
    other_recipient_type = ChoiceField(
        required=False,
        initial=False,
        label=ugettext_noop("Recipient"),
        choices=KEYWORD_RECIPIENT_CHOICES,
    )
    other_recipient_id = ChoiceField(
        required=False,
        label=ugettext_noop("Group Name"),
    )
    other_recipient_message = TrimmedCharField(
        required=False,
        label=ugettext_noop("Message"),
    )
    other_recipient_form_unique_id = ChoiceField(
        required=False,
        label=ugettext_noop("Survey"),
    )
    process_structured_sms = BooleanField(
        required=False,
        label=ugettext_noop("Process incoming keywords as a Structured Message"),
    )
    structured_sms_form_unique_id = ChoiceField(
        required=False,
        label=ugettext_noop("Survey"),
    )
    use_custom_delimiter = BooleanField(
        required=False,
        label=ugettext_noop("Use Custom Delimiter"),
    )
    delimiter = TrimmedCharField(
        required=False,
        label=ugettext_noop("Please Specify Delimiter"),
    )
    use_named_args_separator = BooleanField(
        required=False,
        label=ugettext_noop("Use Joining Character"),
    )
    use_named_args = BooleanField(
        required=False,
        label=ugettext_noop("Use Named Answers"),
    )
    named_args_separator = TrimmedCharField(
        required=False,
        label=ugettext_noop("Please Specify Joining Characcter"),
    )
    named_args = RecordListField(
        input_name="named_args",
        initial=[],
    )

    def __init__(self, *args, **kwargs):
        if 'domain' in kwargs:
            self._cchq_domain = kwargs.pop('domain')

        self.process_structured_sms = False
        if 'process_structured' in kwargs:
            self.process_structured_sms = kwargs.pop('process_structured')

        super(KeywordForm, self).__init__(*args, **kwargs)

        self.fields['sender_content_type'].choices = self.content_type_choices
        self.fields['other_recipient_content_type'].choices = self.content_type_choices

        self.fields['other_recipient_id'].choices = self.group_choices
        self.fields['sender_form_unique_id'].choices = self.form_choices
        self.fields['other_recipient_form_unique_id'].choices = self.form_choices
        self.fields['structured_sms_form_unique_id'].choices = self.form_choices

        from corehq.apps.reminders.views import KeywordsListView
        self.helper = FormHelper()
        self.helper.form_class = "form form-horizontal"

        layout_fields = [
            crispy.Fieldset(
                _('Basic Information'),
                crispy.Field(
                    'keyword',
                    data_bind="value: keyword, "
                              "valueUpdate: 'afterkeydown', "
                              "event: {keyup: updateExampleStructuredSMS}",
                ),
                crispy.Field(
                    'description',
                    data_bind="text: description",
                ),
            ),
        ]
        if self.process_structured_sms:
            layout_fields.append(
                crispy.Fieldset(
                    _("Structured Message Options"),
                    crispy.Field(
                        'structured_sms_form_unique_id',
                        data_bind="value: structured_sms_form_unique_id",
                    ),
                    BootstrapMultiField(
                        _("Delimiters"),
                        crispy.Div(
                            InlineColumnField(
                                'use_custom_delimiter',
                                data_bind="checked: use_custom_delimiter, "
                                          "click: updateExampleStructuredSMS",
                                block_css_class="span2",
                            ),
                            InlineField(
                                'delimiter',
                                data_bind="value: delimiter, "
                                          "valueUpdate: 'afterkeydown', "
                                          "event: {keyup: updateExampleStructuredSMS},"
                                          "visible: use_custom_delimiter",
                                block_css_class="span4",
                            ),
                            css_class="controls-row",
                        ),
                    ),
                    BootstrapMultiField(
                        _("Named Answers"),
                        InlineField(
                            'use_named_args',
                            data_bind="checked: use_named_args, "
                                      "click: updateExampleStructuredSMS",
                        ),
                        ErrorsOnlyField('named_args'),
                        crispy.Div(
                            data_bind="template: {"
                                      " name: 'ko-template-named-args', "
                                      " data: $data"
                                      "}, "
                                      "visible: use_named_args",
                        ),
                    ),
                    BootstrapMultiField(
                        _("Joining Characters"),
                        crispy.Div(
                            InlineColumnField(
                                'use_named_args_separator',
                                data_bind="checked: use_named_args_separator, "
                                          "click: updateExampleStructuredSMS",
                                block_css_class="span2",
                            ),
                            InlineField(
                                'named_args_separator',
                                data_bind="value: named_args_separator, "
                                          "valueUpdate: 'afterkeydown', "
                                          "event: {keyup: updateExampleStructuredSMS},"
                                          "visible: useJoiningCharacter",
                                block_css_class="span4",
                            ),
                            css_class="controls-row",
                        ),
                        data_bind="visible: use_named_args",
                    ),
                    BootstrapMultiField(
                        _("Example Structured Message"),
                        crispy.HTML('<pre style="background: white;" '
                                    'data-bind="text: example_structured_sms">'
                                    '</pre>'),
                    ),
                ),
            )
        layout_fields.extend([
            crispy.Fieldset(
                _("Response"),
                crispy.Field(
                    'sender_content_type',
                    data_bind="value: sender_content_type",
                ),
                crispy.Div(
                    crispy.Field(
                        'sender_message',
                        data_bind="text: sender_message",
                    ),
                    data_bind="visible: isMessageSMS",
                ),
                crispy.Div(
                    crispy.Field(
                        'sender_form_unique_id',
                        data_bind="value: sender_form_unique_id"
                    ),
                    data_bind="visible: isMessageSurvey",
                ),
                crispy.Field(
                    'other_recipient_content_type',
                    data_bind="value: other_recipient_content_type",
                ),
                BootstrapMultiField(
                    "",
                    crispy.Div(
                        crispy.HTML(
                            '<h4 style="margin-bottom: 20px;">%s</h4>'
                            % _("Recipient Information"),
                        ),
                        crispy.Field(
                            'other_recipient_type',
                            data_bind="value: other_recipient_type",
                        ),
                        crispy.Div(
                            crispy.Field(
                                'other_recipient_id',
                                data_bind="value: other_recipient_id",
                            ),
                            data_bind="visible: showRecipientGroup",
                        ),
                        crispy.Div(
                            crispy.Field(
                                'other_recipient_message',
                                data_bind="value: other_recipient_message",
                            ),
                            data_bind="visible: other_recipient_content_type() == 'sms'",
                        ),
                        crispy.Div(
                            crispy.Field(
                                'other_recipient_form_unique_id',
                                data_bind="value: other_recipient_form_unique_id",
                            ),
                            data_bind="visible: other_recipient_content_type() == 'survey'",
                        ),
                        css_class="well",
                        data_bind="visible: notify_others",
                    ),
                ),
            ),
            crispy.Fieldset(
                _("Advanced Options"),
                crispy.Field(
                    'override_open_sessions',
                    data_bind="checked: override_open_sessions",
                ),
                'allow_keyword_use_by',
            ),
            FormActions(
                StrictButton(
                    _("Save Keyword"),
                    css_class='btn-primary',
                    type='submit',
                ),
                crispy.HTML('<a href="%s" class="btn">Cancel</a>'
                            % reverse(KeywordsListView.urlname, args=[self._cchq_domain]))
            ),
        ])
        self.helper.layout = crispy.Layout(*layout_fields)

    @property
    def content_type_choices(self):
        return KEYWORD_CONTENT_CHOICES

    @property
    @memoized
    def group_choices(self):
        group_ids = Group.ids_by_domain(self._cchq_domain)
        groups = []
        for group_doc in iter_docs(Group.get_db(), group_ids):
            groups.append((group_doc['_id'], group_doc['name']))
        return groups

    @property
    @memoized
    def form_choices(self):
        return form_choices(self._cchq_domain)

    @property
    def current_values(self):
        values = {}
        for field_name in self.fields.keys():
            values[field_name] = self[field_name].value()
        return values

    def clean_keyword(self):
        value = self.cleaned_data.get("keyword")
        if value is not None:
            value = value.strip().upper()
        if value is None or value == "":
            raise ValidationError(_("This field is required."))
        if len(value.split()) > 1:
            raise ValidationError(_("Keyword should be one word."))
        duplicate = SurveyKeyword.get_keyword(self._cchq_domain, value)
        if duplicate is not None and duplicate._id != self._sk_id:
            raise ValidationError(_("Keyword already exists."))
        return value

    def clean_sender_message(self):
        value = self.cleaned_data.get("sender_message")
        if self.cleaned_data.get("sender_content_type") == METHOD_SMS:
            if value is None or value == "":
                raise ValidationError(_("This field is required."))
            return value
        else:
            return None

    def clean_sender_form_unique_id(self):
        value = self.cleaned_data.get("sender_form_unique_id")
        if self.cleaned_data.get("sender_content_type") == METHOD_SMS_SURVEY:
            if value is None:
                raise ValidationError(_(
                    "Please create a form first, and then add a keyword "
                    "for it."
                ))
            validate_form_unique_id(value, self._cchq_domain)
            return value
        else:
            return None

    def clean_other_recipient_message(self):
        value = self.cleaned_data.get("other_recipient_message")
        if self.cleaned_data.get("other_recipient_content_type") == METHOD_SMS:
            if value is None or value == "":
                raise ValidationError(_("This field is required."))
            return value
        else:
            return None

    def clean_other_recipient_form_unique_id(self):
        value = self.cleaned_data.get("other_recipient_form_unique_id")
        if self.cleaned_data.get("other_recipient_content_type") == METHOD_SMS_SURVEY:
            if value is None:
                raise ValidationError(_(
                    "Please create a form first, and then "
                    "add a keyword for it."
                ))
            validate_form_unique_id(value, self._cchq_domain)
            return value
        else:
            return None

    def clean_structured_sms_form_unique_id(self):
        value = self.cleaned_data.get("structured_sms_form_unique_id")
        if self.process_structured_sms:
            if value is None:
                raise ValidationError(_(
                    "Please create a form first, and then add a "
                    "keyword for it."
                ))
            validate_form_unique_id(value, self._cchq_domain)
            return value
        else:
            return None

    def clean_delimiter(self):
        value = self.cleaned_data.get("delimiter", None)
        if self.process_structured_sms and self.cleaned_data["use_custom_delimiter"]:
            if value is None or value == "":
                raise ValidationError(_("This field is required."))
            return value
        else:
            return None

    def clean_named_args(self):
        if self.process_structured_sms and self.cleaned_data["use_named_args"]:
            use_named_args_separator = self.cleaned_data["use_named_args_separator"]
            value = self.cleaned_data.get("named_args")
            data_dict = {}
            for d in value:
                name = d["name"].strip().upper()
                xpath = d["xpath"].strip()
                if name == "" or xpath == "":
                    raise ValidationError(_(
                        "Name and xpath are both required fields."
                    ))
                for k, v in data_dict.items():
                    if (not use_named_args_separator
                        and (k.startswith(name) or name.startswith(k))
                    ):
                        raise ValidationError(
                            _("Cannot have two names overlap: ") + "(%s, %s)"
                            % (k, name)
                        )
                    if use_named_args_separator and k == name:
                        raise ValidationError(
                            _("Cannot use the same name twice: ") + name
                        )
                    if v == xpath:
                        raise ValidationError(
                            _("Cannot reference the same xpath twice: ") + xpath
                        )
                data_dict[name] = xpath
            return data_dict
        else:
            return {}

    def clean_named_args_separator(self):
        value = self.cleaned_data["named_args_separator"]
        if (self.process_structured_sms
            and self.cleaned_data["use_named_args"]
            and self.cleaned_data["use_named_args_separator"]
        ):
            if value is None or value == "":
                raise ValidationError(_("This field is required."))
            if value == self.cleaned_data["delimiter"]:
                raise ValidationError(_(
                    "Delimiter and joining character cannot be the same."
                ))
            return value
        else:
            return None

    def clean_other_recipient_type(self):
        if self.cleaned_data['other_recipient_content_type'] == NO_RESPONSE:
            return None
        value = self.cleaned_data["other_recipient_type"]
        if value == RECIPIENT_OWNER:
            if self.cleaned_data['allow_keyword_use_by'] != 'cases':
                raise ValidationError(_(
                    "In order to send to the case's owner you must restrict "
                    "keyword initiation only to cases."
                ))
        return value

    def clean_other_recipient_id(self):
        if self.cleaned_data['other_recipient_content_type'] == NO_RESPONSE:
            return None
        value = self.cleaned_data["other_recipient_id"]
        recipient_type = self.cleaned_data.get("other_recipient_type", None)
        if recipient_type == RECIPIENT_USER_GROUP:
            try:
                g = Group.get(value)
                assert g.doc_type == "Group"
                assert g.domain == self._cchq_domain
            except Exception:
                raise ValidationError("Invalid Group.")
            return value
        else:
            return None


class BroadcastForm(Form):
    recipient_type = ChoiceField(
        required=True,
        label=ugettext_lazy('Recipient'),
        choices=ONE_TIME_RECIPIENT_CHOICES,
    )
    timing = ChoiceField(
        required=True,
        label=ugettext_lazy('Timing'),
        choices=NOW_OR_LATER,
    )
    date = CharField(
        required=False,
        label=ugettext_lazy('Date'),
    )
    time = CharField(
        required=False,
        label=ugettext_lazy('Time'),
    )
    datetime = DateTimeField(
        required=False,
    )
    case_group_id = ChoiceField(
        required=False,
        label=ugettext_lazy('Case Group'),
    )
    user_group_id = ChoiceField(
        required=False,
        label=ugettext_lazy('Mobile Worker Group'),
    )
    location_ids = CharField(
        label='Location(s)',
        required=False,
    )
    include_child_locations = BooleanField(
        required=False,
        label=ugettext_lazy('Also send to users at child locations'),
    )
    content_type = ChoiceField(
        label=ugettext_lazy('Send'),
        choices=((METHOD_SMS, ugettext_lazy("SMS Message")),)
    )
    subject = TrimmedCharField(
        required=False,
        label=ugettext_lazy('Subject'),
        widget=forms.Textarea,
    )
    message = TrimmedCharField(
        required=False,
        label=ugettext_lazy('Message'),
        widget=forms.Textarea,
    )
    form_unique_id = ChoiceField(
        required=False,
        label=ugettext_lazy('Survey'),
    )

    def __init__(self, *args, **kwargs):
        if 'domain' not in kwargs or 'can_use_survey' not in kwargs:
            raise Exception('Expected kwargs: domain, can_use_survey')

        self.domain = kwargs.pop('domain')
        self.can_use_survey = kwargs.pop('can_use_survey')
        super(BroadcastForm, self).__init__(*args, **kwargs)

        if self.can_use_survey:
            add_field_choices(self, 'content_type', [
                (METHOD_SMS_SURVEY, _('SMS Survey')),
            ])

        if toggles.EMAIL_IN_REMINDERS.enabled(self.domain):
            add_field_choices(self, 'content_type', [
                (METHOD_EMAIL, _('Email')),
            ])

        if toggles.BROADCAST_TO_LOCATIONS.enabled(self.domain):
            add_field_choices(self, 'recipient_type', [
                (RECIPIENT_LOCATION, _('Location')),
            ])

        self.fields['form_unique_id'].choices = form_choices(self.domain)
        self.fields['case_group_id'].choices = case_group_choices(self.domain)
        self.fields['user_group_id'].choices = user_group_choices(self.domain)
        self.fields['location_ids'].widget = SupplyPointSelectWidget(
            domain=self.domain,
            multiselect=True,
        )

        self.helper = FormHelper()
        self.helper.form_class = 'form form-horizontal'

        from corehq.apps.reminders.views import BroadcastListView
        layout_fields = [
            crispy.Fieldset(
                _('Recipient'),
                *self.crispy_recipient_fields
            ),
            crispy.Fieldset(
                _('Timing'),
                *self.crispy_timing_fields
            ),
            crispy.Fieldset(
                _('Content'),
                *self.crispy_content_fields
            ),
            FormActions(
                StrictButton(
                    _("Save"),
                    css_class='btn-primary',
                    type='submit',
                ),
                crispy.HTML('<a href="%s" class="btn">Cancel</a>'
                            % reverse(BroadcastListView.urlname, args=[self.domain]))
            ),
        ]
        self.helper.layout = crispy.Layout(*layout_fields)

    @property
    def crispy_recipient_fields(self):
        return [
            crispy.Field(
                'recipient_type',
                data_bind="value: recipient_type",
            ),
            crispy.Div(
                crispy.Field(
                    'case_group_id',
                    data_bind='value: case_group_id',
                ),
                data_bind='visible: showCaseGroupSelect',
            ),
            crispy.Div(
                crispy.Field(
                    'user_group_id',
                    data_bind='value: user_group_id',
                ),
                data_bind='visible: showUserGroupSelect',
            ),
            crispy.Div(
                crispy.Field(
                    'location_ids',
                ),
                crispy.Field(
                    'include_child_locations',
                ),
                data_bind='visible: showLocationSelect',
            ),
        ]

    @property
    def crispy_timing_fields(self):
        return [
            crispy.Field(
                'timing',
                data_bind='value: timing',
            ),
            crispy.Div(
                BootstrapMultiField(
                    _("Date and Time"),
                    InlineField(
                        'date',
                        data_bind='value: date',
                        css_class="input-small",
                    ),
                    crispy.Div(
                        template='reminders/partial/time_picker.html',
                    ),
                ),
                ErrorsOnlyField('time'),
                ErrorsOnlyField('datetime'),
                data_bind='visible: showDateAndTimeSelect',
            ),
        ]

    @property
    def crispy_content_fields(self):
        return [
            crispy.Field(
                'content_type',
                data_bind='value: content_type',
            ),
            crispy.Div(
                crispy.Field(
                    'subject',
                    data_bind='value: subject',
                    style='height: 50px;',
                ),
                data_bind='visible: showSubject',
            ),
            crispy.Div(
                crispy.Field(
                    'message',
                    data_bind='value: message',
                    style='height: 50px;',
                ),
                data_bind='visible: showMessage',
            ),
            crispy.Div(
                crispy.Field(
                    'form_unique_id',
                    data_bind='value: form_unique_id',
                ),
                data_bind='visible: showSurveySelect',
            ),
        ]

    @property
    def project_timezone(self):
        return get_timezone_for_user(None, self.domain)

    def clean_date(self):
        if self.cleaned_data.get('timing') == SEND_NOW:
            return None
        else:
            value = self.cleaned_data.get('date')
            return validate_date(value)

    def clean_time(self):
        if self.cleaned_data.get('timing') == SEND_NOW:
            return None
        else:
            value = self.cleaned_data.get('time')
            return validate_time(value)

    def clean_datetime(self):
        utcnow = datetime.utcnow()
        if self.cleaned_data.get('timing') == SEND_NOW:
            value = utcnow + timedelta(minutes=1)
        else:
            dt = self.cleaned_data.get('date')
            tm = self.cleaned_data.get('time')
            if not isinstance(dt, date) or not isinstance(tm, time):
                # validation didn't pass on the date or time fields
                return None
            value = datetime.combine(dt, tm)
            value = UserTime(value, self.project_timezone).server_time().done().replace(tzinfo=None)
            if value < utcnow:
                raise ValidationError(_('Date and time cannot occur in the past.'))
        return value

    def clean_case_group_id(self):
        if self.cleaned_data.get('recipient_type') == RECIPIENT_SURVEY_SAMPLE:
            value = self.cleaned_data.get('case_group_id')
            return clean_case_group_id(value, self.domain)
        else:
            return None

    def clean_user_group_id(self):
        if self.cleaned_data.get('recipient_type') == RECIPIENT_USER_GROUP:
            value = self.cleaned_data.get('user_group_id')
            return clean_group_id(value, self.domain)
        else:
            return None

    def clean_subject(self):
        value = None
        if self.cleaned_data.get('content_type') == METHOD_EMAIL:
            value = self.cleaned_data.get('subject')
            if not value:
                raise ValidationError('This field is required.')
        return value

    def clean_message(self):
        value = None
        if self.cleaned_data.get('content_type') in (METHOD_SMS, METHOD_EMAIL):
            value = self.cleaned_data.get('message')
            if not value:
                raise ValidationError('This field is required.')
        return value

    def clean_form_unique_id(self):
        if self.cleaned_data.get('content_type') == METHOD_SMS_SURVEY:
            value = self.cleaned_data.get('form_unique_id')
            return validate_form_unique_id(value, self.domain)
        else:
            return None

    def clean_location_ids(self):
        if self.cleaned_data.get('recipient_type') != RECIPIENT_LOCATION:
            return []

        value = self.cleaned_data.get('location_ids')
        if not isinstance(value, basestring) or value.strip() == '':
            raise ValidationError(_('Please choose at least one location'))

        location_ids = [location_id.strip() for location_id in value.split(',')]
        try:
            locations = get_locations_from_ids(location_ids, self.domain)
        except SQLLocation.DoesNotExist:
            raise ValidationError(_('One or more of the locations was not found.'))

        return [location.location_id for location in locations]

    @property
    def current_values(self):
        values = {}
        for field_name in self.fields.keys():
            values[field_name] = self[field_name].value()
        return values
