from __future__ import absolute_import
import re
from corehq.apps.data_interfaces.forms import CaseRuleCriteriaForm
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
from django.forms.widgets import Textarea, CheckboxSelectMultiple
from django.utils.functional import cached_property
from dimagi.utils.django.fields import TrimmedCharField
from django.utils.translation import ugettext_lazy as _, ugettext
from corehq.apps.casegroups.models import CommCareCaseGroup
from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.locations.models import SQLLocation
from corehq.apps.translations.models import StandaloneTranslationDoc
from corehq.apps.users.models import CommCareUser
from corehq.messaging.scheduling.exceptions import ImmediateMessageEditAttempt, UnsupportedScheduleError
from corehq.messaging.scheduling.models import (
    Schedule,
    AlertSchedule,
    TimedSchedule,
    ImmediateBroadcast,
    ScheduledBroadcast,
    SMSContent,
)
from corehq.messaging.scheduling.scheduling_partitioned.models import ScheduleInstance, CaseScheduleInstanceMixin
from couchdbkit.resource import ResourceNotFound
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

    STOP_AFTER_OCCURRENCES = 'after_occurrences'
    STOP_NEVER = 'never'

    CONTENT_SMS = 'sms'
    CONTENT_EMAIL = 'email'
    CONTENT_SMS_SURVEY = 'sms_survey'
    CONTENT_IVR_SURVEY = 'ivr_survey'

    send_frequency = ChoiceField(
        required=True,
        label=_('Send'),
        choices=(
            (SEND_IMMEDIATELY, _('Immediately')),
            (SEND_DAILY, _('Daily')),
            (SEND_WEEKLY, _('Weekly')),
            (SEND_MONTHLY, _('Monthly')),
        )
    )
    weekdays = MultipleChoiceField(
        required=False,
        label=_('On'),
        choices=(
            ('6', _('Sunday')),
            ('0', _('Monday')),
            ('1', _('Tuesday')),
            ('2', _('Wednesday')),
            ('3', _('Thursday')),
            ('4', _('Friday')),
            ('5', _('Saturday')),
        ),
        widget=CheckboxSelectMultiple()
    )
    days_of_month = MultipleChoiceField(
        required=False,
        label=_('On Days'),
        choices=(
            # The actual choices are rendered by a template
            tuple((str(x), '') for x in range(-3, 0)) +
            tuple((str(x), '') for x in range(1, 29))
        )
    )
    send_time = CharField(required=False)
    stop_type = ChoiceField(
        required=False,
        choices=(
            # The text for STOP_AFTER_OCCURRENCES gets set dynamically
            (STOP_AFTER_OCCURRENCES, ''),
            (STOP_NEVER, _('Never')),
        )
    )
    occurrences = IntegerField(
        required=False,
        min_value=1,
        label='',
    )
    recipient_types = MultipleChoiceField(
        required=True,
        label=_('Recipient(s)'),
        choices=(
            (ScheduleInstance.RECIPIENT_TYPE_MOBILE_WORKER, _("Users")),
            (ScheduleInstance.RECIPIENT_TYPE_USER_GROUP, _("User Groups")),
            (ScheduleInstance.RECIPIENT_TYPE_LOCATION, _("User Organizations")),
            (ScheduleInstance.RECIPIENT_TYPE_CASE_GROUP, _("Case Groups")),
        )
    )
    user_recipients = RecipientField(
        required=False,
        label=_("User Recipient(s)"),
    )
    user_group_recipients = RecipientField(
        required=False,
        label=_("User Group Recipient(s)"),
    )
    user_organization_recipients = RecipientField(
        required=False,
        label=_("User Organization Recipient(s)"),
    )
    include_descendant_locations = BooleanField(
        required=False,
        label=_("Also send to users at child locations"),
    )
    case_group_recipients = RecipientField(
        required=False,
        label=_("Case Group Recipient(s)"),
    )
    content = ChoiceField(
        required=True,
        label=_("What to send"),
        choices=(
            (CONTENT_SMS, _('SMS')),
            # (CONTENT_EMAIL, _('Email')),
            # (CONTENT_SMS_SURVEY, _('SMS Survey')),
            # (CONTENT_IVR_SURVEY, _('IVR Survey')),
        )
    )
    translate = BooleanField(
        label=_("Translate this message"),
        required=False
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

    def add_initial_for_timed_schedule(self, initial):
        initial['send_time'] = self.initial_schedule.memoized_events[0].time.strftime('%H:%M')
        if self.initial_schedule.total_iterations == TimedSchedule.REPEAT_INDEFINITELY:
            initial['stop_type'] = self.STOP_NEVER
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
            result['translate'] = '*' not in content.message
            result['non_translated_message'] = content.message.get('*', '')
            for lang in self.project_languages:
                result['message_%s' % lang] = content.message.get(lang, '')

    def compute_initial(self):
        result = {}
        schedule = self.initial_schedule
        if schedule:
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

    @property
    def readonly_mode(self):
        return False

    def __init__(self, domain, schedule, *args, **kwargs):
        self.domain = domain
        self.initial_schedule = schedule

        if kwargs.get('initial'):
            raise ValueError("Initial values are set by the form")

        initial = {}
        if schedule:
            initial = self.compute_initial()
            kwargs['initial'] = initial

        super(ScheduleForm, self).__init__(*args, **kwargs)

        if initial.get('send_frequency'):
            self.update_send_frequency_choices(initial.get('send_frequency'))

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.form_class = 'form form-horizontal'
        self.helper.label_class = 'col-sm-2 col-md-2 col-lg-2'
        self.helper.field_class = 'col-sm-10 col-md-7 col-lg-5'
        self.add_content_fields()

        if self.readonly_mode:
            for field_name, field in self.fields.items():
                field.disabled = True

        self.helper.layout = crispy.Layout(*self.get_layout_fields())

    def get_layout_fields(self):
        return [
            crispy.Fieldset(
                ugettext("Scheduling"),
                *self.get_scheduling_layout_fields()
            ),
            crispy.Fieldset(
                ugettext("Recipients"),
                *self.get_recipients_layout_fields()
            ),
            crispy.Fieldset(
                ugettext("Content"),
                *self.get_content_layout_fields()
            )
        ]

    def get_timing_layout_fields(self):
        raise NotImplementedError()

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
                ugettext("On Days"),
                crispy.Field(
                    'days_of_month',
                    template='scheduling/partial/days_of_month_picker.html',
                ),
                data_bind='visible: showDaysOfMonthInput',
            ),
        ]

        result.extend(self.get_timing_layout_fields())

        result.extend([
            hqcrispy.B3MultiField(
                ugettext("Stop"),
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
                    data_bind="visible: stop_type() != '%s'" % self.STOP_NEVER,
                ),
                data_bind='visible: showStopInput',
            ),
            hqcrispy.B3MultiField(
                "",
                crispy.HTML(
                    '<span>%s</span> <span data-bind="text: computedEndDate"></span>'
                    % ugettext("Date of final occurrence:"),
                ),
                data_bind="visible: computedEndDate() !== ''",
            ),
        ])

        return result

    def get_recipients_layout_fields(self):
        return [
            hqcrispy.B3MultiField(
                ugettext("Recipient(s)"),
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
        result = [
            crispy.Field('content'),
            crispy.Field('translate', data_bind='checked: translate'),
            crispy.Div(
                crispy.Field('non_translated_message'),
                data_bind='visible: !translate()',
            ),
        ]

        translated_fields = [crispy.Field('message_%s' % lang) for lang in self.project_languages]
        result.append(
            crispy.Div(*translated_fields, data_bind='visible: translate()')
        )

        return result

    @cached_property
    def project_languages(self):
        doc = StandaloneTranslationDoc.get_obj(self.domain, 'sms')
        return getattr(doc, 'langs', ['en'])

    def add_content_fields(self):
        self.fields['non_translated_message'] = CharField(label=_("Message"), required=False, widget=Textarea)

        for lang in self.project_languages:
            # TODO support RTL languages
            self.fields['message_%s' % lang] = CharField(
                label="{} ({})".format(_("Message"), lang), required=False, widget=Textarea
            )

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
        if self.cleaned_data.get('send_frequency') == self.SEND_IMMEDIATELY:
            return None

        return validate_time(self.cleaned_data.get('send_time'))

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

    def distill_content(self):
        form_data = self.cleaned_data
        if form_data['translate']:
            messages = {}
            for lang in self.project_languages:
                key = 'message_%s' % lang
                if key in form_data:
                    messages[lang] = form_data[key]
            content = SMSContent(message=messages)
        else:
            content = SMSContent(message={'*': form_data['non_translated_message']})

        return content

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

        return form_data['occurrences']

    def distill_extra_scheduling_options(self):
        form_data = self.cleaned_data
        return {
            'include_descendant_locations': (
                ScheduleInstance.RECIPIENT_TYPE_LOCATION in form_data['recipient_types'] and
                form_data['include_descendant_locations']
            ),
        }

    def distill_start_offset(self):
        raise NotImplementedError()

    def distill_start_day_of_week(self):
        raise NotImplementedError()

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
                form_data['send_time'],
                content,
                total_iterations=total_iterations,
                start_offset=self.distill_start_offset(),
                extra_options=extra_scheduling_options,
            )
        else:
            schedule = TimedSchedule.create_simple_daily_schedule(
                self.domain,
                form_data['send_time'],
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
                form_data['send_time'],
                content,
                form_data['weekdays'],
                self.distill_start_day_of_week(),
                total_iterations=total_iterations,
                extra_options=extra_scheduling_options,
            )
        else:
            schedule = TimedSchedule.create_simple_weekly_schedule(
                self.domain,
                form_data['send_time'],
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
                form_data['send_time'],
                sorted_days_of_month,
                content,
                total_iterations=total_iterations,
                extra_options=extra_scheduling_options,
            )
        else:
            schedule = TimedSchedule.create_simple_monthly_schedule(
                self.domain,
                form_data['send_time'],
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
        label=_('Schedule Name'),
        max_length=1000,
    )

    start_date = CharField(
        label='',
        required=False
    )

    def __init__(self, domain, schedule, broadcast, *args, **kwargs):
        self.initial_broadcast = broadcast
        super(BroadcastForm, self).__init__(domain, schedule, *args, **kwargs)

    def get_layout_fields(self):
        result = super(BroadcastForm, self).get_layout_fields()
        if not self.readonly_mode:
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

    def get_timing_layout_fields(self):
        return [
            hqcrispy.B3MultiField(
                ugettext("At"),
                crispy.Field(
                    'send_time',
                    template='scheduling/partial/time_picker.html',
                ),
                data_bind='visible: showTimeInput',
            ),
            hqcrispy.B3MultiField(
                ugettext("Start"),
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

    @property
    def readonly_mode(self):
        return isinstance(self.initial_broadcast, ImmediateBroadcast)

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

    SEND_TIME_SPECIFIC_TIME = 'SPECIFIC_TIME'

    START_DATE_RULE_TRIGGER = 'RULE_TRIGGER'

    START_OFFSET_ZERO = 'ZERO'
    START_OFFSET_NEGATIVE = 'NEGATIVE'
    START_OFFSET_POSITIVE = 'POSITIVE'

    send_time_type = ChoiceField(
        required=True,
        choices=(
            (SEND_TIME_SPECIFIC_TIME, _("A specific time")),
        )
    )

    start_date_type = ChoiceField(
        required=True,
        choices=(
            (START_DATE_RULE_TRIGGER, _("The date the rule is satisfied")),
        )
    )

    start_offset_type = ChoiceField(
        required=False,
        choices=(
            (START_OFFSET_ZERO, _("Exactly on the start date")),
            (START_OFFSET_NEGATIVE, _("Before the start date by")),
            (START_OFFSET_POSITIVE, _("After the start date by")),
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
            ('6', _('The first Sunday that occurs on or after the start date')),
            ('0', _('The first Monday that occurs on or after the start date')),
            ('1', _('The first Tuesday that occurs on or after the start date')),
            ('2', _('The first Wednesday that occurs on or after the start date')),
            ('3', _('The first Thursday that occurs on or after the start date')),
            ('4', _('The first Friday that occurs on or after the start date')),
            ('5', _('The first Saturday that occurs on or after the start date')),
        ),
    )

    custom_recipient = ChoiceField(
        required=False,
        choices=(
            (k, v[1])
            for k, v in settings.AVAILABLE_CUSTOM_SCHEDULING_RECIPIENTS.items()
        )
    )

    def __init__(self, domain, schedule, rule, criteria_form, *args, **kwargs):
        self.initial_rule = rule
        self.criteria_form = criteria_form
        super(ConditionalAlertScheduleForm, self).__init__(domain, schedule, *args, **kwargs)
        self.update_recipient_types_choices()

    def update_recipient_types_choices(self):
        new_choices = [
            (CaseScheduleInstanceMixin.RECIPIENT_TYPE_SELF, _("The Case")),
            (CaseScheduleInstanceMixin.RECIPIENT_TYPE_CASE_OWNER, _("The Case's Owner")),
        ]
        new_choices.extend(self.fields['recipient_types'].choices)

        if (
            self.criteria_form.is_system_admin or
            CaseScheduleInstanceMixin.RECIPIENT_TYPE_CUSTOM in self.initial['recipient_types']
        ):
            new_choices.extend([
                (CaseScheduleInstanceMixin.RECIPIENT_TYPE_CUSTOM, _("Custom Recipient")),
            ])

        self.fields['recipient_types'].choices = new_choices

    def add_initial_recipients(self, recipients, initial):
        super(ConditionalAlertScheduleForm, self).add_initial_recipients(recipients, initial)

        for recipient_type, recipient_id in recipients:
            if recipient_type == CaseScheduleInstanceMixin.RECIPIENT_TYPE_CUSTOM:
                initial['custom_recipient'] = recipient_id

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

        if self.initial_rule:
            self.add_initial_recipients(self.initial_rule.memoized_actions[0].definition.recipients, result)

        return result

    def get_timing_layout_fields(self):
        return [
            hqcrispy.B3MultiField(
                ugettext("At"),
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
                    data_bind="visible: send_time_type() === '%s'" % self.SEND_TIME_SPECIFIC_TIME,
                ),
                data_bind="visible: showTimeInput",
            ),
            hqcrispy.B3MultiField(
                ugettext("Start Date"),
                crispy.Div(
                    twbscrispy.InlineField(
                        'start_date_type',
                        data_bind='value: start_date_type',
                    ),
                    css_class='col-sm-4',
                ),
                data_bind='visible: showStartDateInput',
            ),
            hqcrispy.B3MultiField(
                ugettext("Begin"),
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
                    crispy.HTML("<span>%s</span>" % ugettext("days(s)")),
                    data_bind="visible: start_offset_type() !== '%s'" % self.START_OFFSET_ZERO,
                ),
                data_bind="visible: send_frequency() === '%s'" % self.SEND_DAILY,
            ),
            hqcrispy.B3MultiField(
                ugettext("Begin"),
                twbscrispy.InlineField('start_day_of_week'),
                data_bind="visible: send_frequency() === '%s'" % self.SEND_WEEKLY,
            ),
        ]

    def get_recipients_layout_fields(self):
        result = super(ConditionalAlertScheduleForm, self).get_recipients_layout_fields()
        result.extend([
            hqcrispy.B3MultiField(
                ugettext("Custom Recipient"),
                twbscrispy.InlineField('custom_recipient'),
                self.get_system_admin_label(),
                data_bind="visible: recipientTypeSelected('%s')" % CaseScheduleInstanceMixin.RECIPIENT_TYPE_CUSTOM,
            ),
        ])
        return result

    def get_system_admin_label(self):
        return crispy.HTML("""
            <label class="col-xs-1 control-label">
                <span class="label label-primary">%s</span>
            </label>
        """ % ugettext("Requires System Admin"))

    def clean_send_time(self):
        if self.cleaned_data.get('send_time_type') == self.SEND_TIME_SPECIFIC_TIME:
            return super(ConditionalAlertScheduleForm, self).clean_send_time()

        return None

    def clean_start_offset_type(self):
        if self.cleaned_data.get('send_frequency') != self.SEND_DAILY:
            return None

        value = self.cleaned_data.get('start_offset_type')

        if not value:
            raise ValidationError(ugettext("This field is required"))

        if (
            value == self.START_OFFSET_NEGATIVE and
            self.cleaned_data.get('start_date_type') == self.START_DATE_RULE_TRIGGER
        ):
            raise ValidationError(ugettext("You may not start sending before the day that the rule triggers."))

        return value

    def clean_start_day_of_week(self):
        if self.cleaned_data.get('send_frequency') != self.SEND_WEEKLY:
            return TimedSchedule.ANY_DAY

        value = self.cleaned_data.get('start_day_of_week')
        error = ValidationError(ugettext("Invalid choice selected"))

        try:
            value = int(value)
        except (ValueError, TypeError):
            raise error

        if value < 0 or value > 6:
            raise error

        return value

    def clean_custom_recipient(self):
        recipient_types = self.cleaned_data.get('recipient_types')
        custom_recipient = self.cleaned_data.get('custom_recipient')

        if CaseScheduleInstanceMixin.RECIPIENT_TYPE_CUSTOM not in recipient_types:
            return None

        if not custom_recipient:
            raise ValidationError(ugettext("This field is required"))

        return custom_recipient

    def distill_start_offset(self):
        send_frequency = self.cleaned_data.get('send_frequency')
        start_offset_type = self.cleaned_data.get('start_offset_type')

        if (
            send_frequency == self.SEND_DAILY and
            start_offset_type in (self.START_OFFSET_NEGATIVE, self.START_OFFSET_POSITIVE)
        ):

            start_offset = self.cleaned_data.get('start_offset')

            if start_offset is None:
                raise ValidationError(ugettext("This field is required"))

            if start_offset_type == self.START_OFFSET_NEGATIVE:
                return -1 * start_offset
            else:
                return start_offset

        return 0

    def distill_start_day_of_week(self):
        return self.cleaned_data['start_day_of_week']

    def distill_scheduler_module_info(self):
        return CreateScheduleInstanceActionDefinition.SchedulerModuleInfo(enabled=False)

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

    def create_rule_action(self, rule, schedule):
        fields = {
            'recipients': self.distill_recipients(),
            'reset_case_property_name': None,
            'scheduler_module_info': self.distill_scheduler_module_info(),
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
        action_definition.reset_case_property_name = None
        action_definition.scheduler_module_info = self.distill_scheduler_module_info()
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
        label=_("Name"),
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
