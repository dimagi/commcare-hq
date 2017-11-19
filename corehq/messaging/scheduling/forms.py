from __future__ import absolute_import
import re
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

from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.translations.models import StandaloneTranslationDoc
from corehq.apps.users.models import CommCareUser
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
    recipients = RecipientField(
        label=_("Recipient(s)"),
        help_text=_("Type a username, group name or location"),
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
                ugettext(""),
                crispy.HTML(
                    '<span>%s</span> <span data-bind="text: computedEndDate"></span>'
                    % ugettext("Date of final occurrence:"),
                ),
                data_bind="visible: computedEndDate() !== ''",
            ),
        ]

    def get_recipients_layout_fields(self):
        return [
            crispy.Field(
                'recipients',
                data_bind='value: message_recipients.value',
                placeholder=_("Select some recipients")
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

    def clean_recipients(self):
        data = self.cleaned_data['recipients']
        # TODO Will need to add more than user ids
        # TODO batch id verification
        for user_id in data:
            user = CommCareUser.get_db().get(user_id)
            assert user['domain'] == self.domain, "User must be in the same domain"

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
