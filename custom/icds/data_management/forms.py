from django import forms
from django.utils.translation import ugettext_lazy

from crispy_forms import layout as crispy
from crispy_forms.layout import Submit

from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.hqwebapp.crispy import HQFormHelper
from corehq.sql_db.util import get_db_aliases_for_partitioned_query
from custom.icds.data_management.base import SQLBasedDataManagement
from custom.icds.data_management.const import DATA_MANAGEMENT_TASKS
from custom.icds.data_management.models import DataManagementRequest
from custom.icds.data_management.tasks import execute_data_management


class DataManagementForm(forms.Form):
    slug = forms.ChoiceField(label=ugettext_lazy("Data Management"), choices=(
        (pull.slug, pull.name) for pull in DATA_MANAGEMENT_TASKS.values()
    ))
    db_alias = forms.ChoiceField(label=ugettext_lazy("DB partition"), choices=(
        (db_alias, db_alias) for db_alias in get_db_aliases_for_partitioned_query()
    ))
    start_date = forms.DateField(required=False, widget=forms.DateInput())
    end_date = forms.DateField(required=False, widget=forms.DateInput())

    def __init__(self, request, domain, *args, **kwargs):
        self.domain = domain
        super(DataManagementForm, self).__init__(*args, **kwargs)
        self.helper = HQFormHelper()
        self.helper.layout = crispy.Layout(
            crispy.Field('slug'),
            crispy.Field('db_alias'),
            crispy.Field('start_date', css_class="date-picker"),
            crispy.Field('end_date', css_class="date-picker"),
            hqcrispy.FormActions(
                crispy.ButtonHolder(
                    Submit('submit', ugettext_lazy("Submit"))
                )
            )
        )

    def clean_start_date(self):
        start_date = self.cleaned_data['start_date']
        slug = self.cleaned_data['slug']
        if not start_date and issubclass(DATA_MANAGEMENT_TASKS[slug], SQLBasedDataManagement):
            self.add_error("start_date", "Start date needed to run SQL based tasks")
        return start_date

    def clean(self):
        start_date = self.cleaned_data['start_date']
        end_date = self.cleaned_data['end_date']
        if start_date and end_date and start_date > end_date:
            self.add_error("end_date", "End date should be greater than start date")

    def submit(self, domain, username):
        request = DataManagementRequest.objects.create(
            slug=self.cleaned_data['slug'], domain=domain, db_alias=self.cleaned_data['db_alias'],
            initiated_by=username, start_date=self.cleaned_data['start_date'],
            end_date=self.cleaned_data['end_date']
        )
        execute_data_management.delay(request.id)
