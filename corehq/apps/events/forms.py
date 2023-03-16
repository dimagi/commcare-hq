from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils.translation import gettext_noop

from crispy_forms import layout as crispy
from crispy_forms.layout import Layout

from corehq.apps.events.models import AttendeeCase
from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.hqwebapp.crispy import HQModalFormHelper

TRACK_BY_DAY = "by_day"
TRACK_BY_EVENT = "by_event"

TRACKING_OPTIONS = [
    (TRACK_BY_DAY, _("Per event day")),
    (TRACK_BY_EVENT, _("Per entire event")),
]


class CreateEventForm(forms.Form):
    name = forms.CharField(
        label=_("Name"),
        required=True
    )
    start_date = forms.DateField(
        label=_('Start Date'),
        required=True
    )
    end_date = forms.DateField(
        label=_('End Date'),
        required=True
    )
    attendance_target = forms.IntegerField(
        label=_("Attendance target"),
        help_text=_("The expected amount of attendees."),
        required=True,
        min_value=1,
    )
    sameday_reg = forms.BooleanField(
        label=_("Allow same day registration"),
        required=False,
    )
    tracking_option = forms.ChoiceField(
        label=_("Attendance recording options"),
        choices=TRACKING_OPTIONS,
        widget=forms.RadioSelect,
        required=False,
    )
    expected_attendees = forms.MultipleChoiceField(
        label=_("Attendees"),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        self.domain = kwargs.pop('domain', None)
        event = kwargs.pop('event', None)

        if event:
            kwargs['initial'] = self.compute_initial(event)
        else:
            kwargs['initial'] = None

        super(CreateEventForm, self).__init__(*args, **kwargs)

        self.fields['expected_attendees'].choices = self.get_attendee_choices()

        self.helper = hqcrispy.HQFormHelper()
        self.helper.add_layout(
            crispy.Layout(
                crispy.Fieldset(
                    _("Add Attendance Tracking Event"),
                    crispy.Field('name', data_bind="value: name"),
                    crispy.Field(
                        'start_date',
                        data_bind="value: startDate",
                        css_class='col-sm-4',
                    ),
                    crispy.Field('end_date', data_bind="value: endDate"),
                    crispy.Field('attendance_target', data_bind="value: attendanceTarget"),
                    crispy.Field('sameday_reg', data_bind="checked: sameDayRegistration"),
                    crispy.Div(
                        crispy.Field('tracking_option', data_bind="checked: trackingOption"),
                        data_bind="visible: showTrackingOptions",
                    ),
                    'expected_attendees',
                    hqcrispy.FormActions(
                        crispy.Submit('submit_btn', 'Save')
                    ),
                )
            )
        )

    @property
    def current_values(self):
        return {
            'name': self['name'].value(),
            'start_date': self['start_date'].value(),
            'end_date': self['end_date'].value(),
            'attendance_target': self['attendance_target'].value(),
            'sameday_reg': self['sameday_reg'].value(),
            'tracking_option': self['tracking_option'].value(),
            'expected_attendees': self['expected_attendees'].value(),
        }

    def compute_initial(self, event):
        return {
            'name': event.name,
            'start_date': event.start_date,
            'end_date': event.end_date,
            'attendance_target': event.attendance_target,
            'sameday_reg': event.sameday_reg,
            'tracking_option': TRACK_BY_DAY if event.track_each_day else TRACK_BY_EVENT,
            'expected_attendees': [
                attendee.case_id for attendee in event.get_expected_attendees()
            ],
        }

    def get_new_event_form(self):
        return CreateEventForm.create(self.cleaned_data)

    def clean_tracking_option(self):
        tracking_option = self.cleaned_data.get('tracking_option', TRACK_BY_DAY)
        self.cleaned_data['track_each_day'] = tracking_option == TRACK_BY_DAY
        return self.cleaned_data

    def clean(self):
        cleaned_data = self.cleaned_data
        if cleaned_data['end_date'] < cleaned_data['start_date']:
            raise ValidationError(_("End Date cannot be before Start Date"))

        return cleaned_data

    def get_attendee_choices(self):
        return [
            (attendee.case_id, attendee.name)
            for attendee in AttendeeCase.objects.by_domain(self.domain)
        ]


class NewAttendeeForm(forms.Form):
    name = forms.CharField(
        max_length=255,
        required=True,
        label=gettext_noop('Name'),
    )

    # TODO: Offer external_id?
    #       Support uniqueness validation like NewMobileWorkerForm.username
    # external_id = forms.CharField(
    #     max_length=255,
    #     required=False,
    #     label=gettext_noop('Unique ID'),
    # )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # TODO: Append other case properties to `self.fields`?
        #       Practicality: What if there are _many_ case properties?
        #       Map case property types to field types

        self.helper = HQModalFormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            crispy.Field(
                'name',
                data_bind="value: name, valueUpdate: 'keyup'",
            )
        )
