from __future__ import absolute_import
from builtins import range
import re
from corehq.apps.groups.models import Group
from corehq.apps.hqwebapp import crispy as hqcrispy
from crispy_forms import layout as crispy
from crispy_forms import bootstrap as twbscrispy
from crispy_forms.helper import FormHelper
from dateutil import parser
from django.core.exceptions import ValidationError
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
from django.utils.translation import ugettext_lazy as _, ugettext
from corehq.apps.casegroups.models import CommCareCaseGroup
from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.locations.models import SQLLocation
from corehq.apps.translations.models import StandaloneTranslationDoc
from corehq.apps.users.models import CommCareUser
from couchdbkit.resource import ResourceNotFound
import six


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
    SEND_DAILY = 'daily'
    SEND_WEEKLY = 'weekly'
    SEND_MONTHLY = 'monthly'
    SEND_IMMEDIATELY = 'immediately'

    STOP_AFTER_OCCURRENCES = 'after_occurrences'
    STOP_NEVER = 'never'

    RECIPIENT_TYPE_USER = 'USER'
    RECIPIENT_TYPE_USER_GROUP = 'USER_GROUP'
    RECIPIENT_TYPE_LOCATION = 'LOCATION'
    RECIPIENT_TYPE_CASE_GROUP = 'CASE_GROUP'

    schedule_name = CharField(
        required=True,
        label=_('Schedule Name'),
        max_length=1000,
    )
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
    start_date = CharField(
        label='',
        required=False
    )
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
            (RECIPIENT_TYPE_USER, _("Users")),
            (RECIPIENT_TYPE_USER_GROUP, _("User Groups")),
            (RECIPIENT_TYPE_LOCATION, _("User Organizations")),
            (RECIPIENT_TYPE_CASE_GROUP, _("Case Groups")),
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
            ('sms', _('SMS')),
            # ('email', _('Email')),
            # ('sms_survey', _('SMS Survey')),
            # ('ivr_survey', _('IVR Survey')),
        )
    )
    translate = BooleanField(
        label=_("Translate this message"),
        required=False
    )

    def update_send_frequency_choices(self, initial_value):
        if not initial_value:
            return

        def filter_function(two_tuple):
            if initial_value == self.SEND_IMMEDIATELY:
                return two_tuple[0] == self.SEND_IMMEDIATELY
            else:
                return two_tuple[0] != self.SEND_IMMEDIATELY

        self.fields['send_frequency'].choices = [
            c for c in self.fields['send_frequency'].choices if filter_function(c)
        ]

    def __init__(self, *args, **kwargs):
        self.domain = kwargs.pop('domain')
        initial = kwargs.get('initial')
        readonly = False
        if initial:
            readonly = (initial.get('send_frequency') == self.SEND_IMMEDIATELY)
            message = initial.get('message', {})
            kwargs['initial']['translate'] = '*' not in message
            kwargs['initial']['non_translated_message'] = message.get('*', '')
            for lang in self.project_languages:
                kwargs['initial']['message_%s' % lang] = message.get(lang, '')

        super(ScheduleForm, self).__init__(*args, **kwargs)
        self.update_send_frequency_choices(initial.get('send_frequency') if initial else None)
        self.helper = FormHelper()
        self.helper.form_class = 'form form-horizontal'
        self.helper.label_class = 'col-sm-2 col-md-2 col-lg-2'
        self.helper.field_class = 'col-sm-10 col-md-7 col-lg-5'
        self.add_content_fields()

        if readonly:
            for field_name, field in self.fields.items():
                field.disabled = True

        layout_fields = [
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

        if not readonly:
            layout_fields += [
                hqcrispy.FormActions(
                    twbscrispy.StrictButton(
                        _("Save"),
                        css_class='btn-primary',
                        type='submit',
                    ),
                ),
            ]

        self.helper.layout = crispy.Layout(*layout_fields)

    def get_scheduling_layout_fields(self):
        return [
            crispy.Field('schedule_name'),
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
        ]

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
                data_bind="visible: recipientTypeSelected('%s')" % self.RECIPIENT_TYPE_USER,
            ),
            crispy.Div(
                crispy.Field(
                    'user_group_recipients',
                    data_bind='value: user_group_recipients.value',
                    placeholder=_("Select user group(s)")
                ),
                data_bind="visible: recipientTypeSelected('%s')" % self.RECIPIENT_TYPE_USER_GROUP,
            ),
            crispy.Div(
                crispy.Field(
                    'user_organization_recipients',
                    data_bind='value: user_organization_recipients.value',
                    placeholder=_("Select user organization(s)")
                ),
                crispy.Field('include_descendant_locations'),
                data_bind="visible: recipientTypeSelected('%s')" % self.RECIPIENT_TYPE_LOCATION,
            ),
            crispy.Div(
                crispy.Field(
                    'case_group_recipients',
                    data_bind='value: case_group_recipients.value',
                    placeholder=_("Select case group(s)")
                ),
                data_bind="visible: recipientTypeSelected('%s')" % self.RECIPIENT_TYPE_CASE_GROUP,
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
        if self.RECIPIENT_TYPE_USER not in self.cleaned_data.get('recipient_types', []):
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
        if self.RECIPIENT_TYPE_USER_GROUP not in self.cleaned_data.get('recipient_types', []):
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
        if self.RECIPIENT_TYPE_LOCATION not in self.cleaned_data.get('recipient_types', []):
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
        if self.RECIPIENT_TYPE_CASE_GROUP not in self.cleaned_data.get('recipient_types', []):
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

    def clean_start_date(self):
        if self.cleaned_data.get('send_frequency') == self.SEND_IMMEDIATELY:
            return None

        return validate_date(self.cleaned_data.get('start_date'))

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
