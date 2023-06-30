from datetime import date

from django import forms
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.utils.translation import gettext_noop

from crispy_forms import layout as crispy
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout

from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.hqwebapp.crispy import HQModalFormHelper
from corehq.apps.locations.forms import LocationSelectWidget
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.util import get_locations_from_ids
from corehq.apps.reports.filters.users import ExpandedMobileWorkerFilter
from corehq.apps.users.dbaccessors import get_mobile_users_by_filters
from corehq.apps.users.forms import PrimaryLocationWidget

from .models import EVENT_IN_PROGRESS, EVENT_NOT_STARTED, AttendeeModel

TRACK_BY_DAY = "by_day"
TRACK_BY_EVENT = "by_event"

TRACKING_OPTIONS = [
    (TRACK_BY_DAY, _("Per event day")),
    (TRACK_BY_EVENT, _("Per entire event")),
]


class EventForm(forms.Form):
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
        required=False
    )
    location_id = forms.CharField(
        label=_('Location'),
        required=False,
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
    attendance_takers = forms.MultipleChoiceField(
        label=_("Attendance Takers"),
        required=True,
        help_text=_("Please choose at least one Attendance Taker")
    )

    def __init__(self, *args, **kwargs):
        self.domain = kwargs.pop('domain', None)
        self.event = kwargs.pop('event', None)

        if self.event:
            kwargs['initial'] = self.compute_initial(self.event)
            self.title_prefix = "Edit"
        else:
            kwargs['initial'] = None
            self.title_prefix = "Add"

        super().__init__(*args, **kwargs)
        self._init_location_id()
        fields_should_be_available = self.determine_field_availability(self.event)
        tracking_option_data_bind = "checked: trackingOption"
        if fields_should_be_available['tracking_option']:
            tracking_option_data_bind += ", attr: {disabled: !showTrackingOptions()}"
        else:
            tracking_option_data_bind += ", attr: {disabled: true}"

        self.helper = hqcrispy.HQFormHelper()
        self.helper.add_layout(
            crispy.Layout(
                crispy.Fieldset(
                    _(f"{self.title_prefix} Attendance Tracking Event"),
                    crispy.Field('name', data_bind="value: name"),
                    crispy.Field(
                        'start_date',
                        data_bind="value: startDate",
                        css_class='col-sm-4',
                    ),
                    crispy.Field('end_date', data_bind="value: endDate"),
                    crispy.Field('location_id'),
                    crispy.Field(
                        'attendance_target',
                        data_bind="value: attendanceTarget",
                    ),
                    crispy.Field(
                        'sameday_reg',
                        data_bind="checked: sameDayRegistration",
                    ),
                    crispy.Div(
                        crispy.Field(
                            'tracking_option',
                            data_bind=tracking_option_data_bind,
                        )
                    ),
                    'expected_attendees',
                    'attendance_takers',
                    hqcrispy.FormActions(
                        crispy.Submit('submit_btn', 'Save')
                    ),
                )
            )
        )

        self.fields['expected_attendees'].choices = self._get_attendee_choices()
        self.fields['attendance_takers'].choices = self._get_possible_attendance_takers_ids()

        self.fields['name'].disabled = not fields_should_be_available['name']
        self.fields['start_date'].disabled = not fields_should_be_available['start_date']
        self.fields['attendance_target'].disabled = not fields_should_be_available['attendance_target']
        self.fields['expected_attendees'].disabled = not fields_should_be_available['expected_attendees']

    @staticmethod
    def determine_field_availability(event):
        not_started = event is None or event.status == EVENT_NOT_STARTED
        in_progress = event and event.status == EVENT_IN_PROGRESS
        no_attendance = (
            not_started
            or in_progress
            and event.total_attendance == 0
        )
        not_completed = not_started or in_progress

        return {
            'name': not_started,
            'start_date': not_started,
            'end_date': not_completed,
            'location_id': no_attendance,
            'attendance_target': no_attendance,
            'sameday_reg': not_completed,
            'tracking_option': no_attendance,
            'expected_attendees': no_attendance,
        }

    @property
    def current_values(self):
        return {
            'name': self['name'].value(),
            'start_date': self['start_date'].value(),
            'end_date': self['end_date'].value(),
            'location_id': self['location_id'].value(),
            'attendance_target': self['attendance_target'].value(),
            'sameday_reg': self['sameday_reg'].value(),
            'tracking_option': self['tracking_option'].value(),
            'expected_attendees': self['expected_attendees'].value(),
            'attendance_takers': self['attendance_takers'].value(),
        }

    def compute_initial(self, event):
        return {
            'name': event.name,
            'start_date': event.start_date,
            'end_date': event.end_date,
            'location_id': event.location_id,
            'attendance_target': event.attendance_target,
            'sameday_reg': event.sameday_reg,
            'tracking_option': TRACK_BY_DAY if event.track_each_day else TRACK_BY_EVENT,
            'expected_attendees': [
                attendee.case_id for attendee in event.get_expected_attendees()
            ],
            'attendance_takers': event.attendance_taker_ids,
        }

    def get_new_event_form(self):
        return EventForm.create(self.cleaned_data)

    def clean_tracking_option(self):
        tracking_option = self.cleaned_data.get('tracking_option', TRACK_BY_DAY)
        self.cleaned_data['track_each_day'] = tracking_option == TRACK_BY_DAY
        return self.cleaned_data

    def clean(self):
        cleaned_data = self.cleaned_data
        if 'start_date' not in cleaned_data:
            raise ValidationError(_("Invalid Start Date"))

        start_date = cleaned_data['start_date']
        end_date = cleaned_data.get('end_date')
        today = date.today()

        if (not self.fields['start_date'].disabled) and today > start_date:
            raise ValidationError(_("You cannot specify the start date in the past"))

        if end_date:
            if end_date < start_date:
                raise ValidationError(_("End Date cannot be before Start Date"))

            if today > end_date:
                raise ValidationError(_("You cannot specify the end date in the past"))

        return cleaned_data

    def _init_location_id(self):
        widget = LocationSelectWidget(
            self.domain,
            id='id_location_id',
            placeholder=_("All Locations"),
            attrs={'data-bind': 'value: locationId'},
        )
        widget.query_url = f"{widget.query_url}?show_all=true"
        help_text = ExpandedMobileWorkerFilter.location_search_help
        self.fields['location_id'].widget = widget
        self.fields['location_id'].help_text = help_text

    def _get_attendee_choices(self):
        if self.event and self.event.location_id:
            models = AttendeeModel.objects.by_location_id(
                self.domain,
                self.event.location_id,
            )
        else:
            models = AttendeeModel.objects.by_domain(self.domain)
        return [(m.case_id, m.name) for m in models]

    def _get_possible_attendance_takers_ids(self):
        attendance_takers_filters = {'user_active_status': True}
        if self.event and self.event.location_id:
            attendance_takers_filters['location_id'] = self.event.location_id
        users = get_mobile_users_by_filters(self.domain, attendance_takers_filters)
        return [(u.user_id, u.raw_username) for u in users]


class NewAttendeeForm(forms.Form):
    name = forms.CharField(
        max_length=255,
        required=True,
        label=gettext_noop('Name'),
    )
    location_id = forms.CharField(
        label=gettext_noop("Location"),
        required=False,
        widget=forms.Select(),
    )

    def __init__(self, *args, domain, **kwargs):
        self.domain = domain
        super().__init__(*args, **kwargs)
        self.helper = HQModalFormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            crispy.Field(
                'name',
                data_bind="value: name",
            ),
            crispy.Field(
                'location_id',
                data_bind='value: location_id',
                data_query_url=reverse('location_search', args=(self.domain,)),
            ),
        )


class EditAttendeeForm(forms.ModelForm):

    class Meta:
        model = AttendeeModel
        fields = ('name', 'locations', 'primary_location')
        help_texts = {
            'locations': ExpandedMobileWorkerFilter.location_search_help,
        }
        widgets = {
            'primary_location': PrimaryLocationWidget(
                css_id='id_primary_location',
                source_css_id='id_locations',
            ),
        }

    def __init__(self, *args, domain, **kwargs):
        self.domain = domain
        super().__init__(*args, **kwargs)
        self.base_fields['locations'].widget = LocationSelectWidget(
            self.domain, multiselect=True, id='id_locations',
        )
        self.helper = FormHelper()
        self.helper.form_method = 'POST'
        self.helper.form_class = 'form-horizontal'
        self.helper.form_tag = False
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'

    def clean_locations(self):
        location_ids = self.data.getlist('locations')
        try:
            locations = get_locations_from_ids(location_ids, self.domain)
        except SQLLocation.DoesNotExist:
            raise ValidationError(
                _('One or more of the locations was not found.')
            )

        return [location.location_id for location in locations]

    def clean(self):
        cleaned_data = super().clean()

        primary_location_id = cleaned_data['primary_location']
        location_ids = cleaned_data['locations']
        if primary_location_id:
            if primary_location_id not in location_ids:
                self.add_error(
                    'primary_location',
                    _("Primary location must be one of the user's locations")
                )
        if location_ids and not primary_location_id:
            self.add_error(
                'primary_location',
                _("Primary location can't be empty if the user has any "
                  "locations set")
            )
