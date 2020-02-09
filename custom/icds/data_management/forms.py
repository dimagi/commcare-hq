from django import forms
from django.utils.translation import ugettext_lazy

from crispy_forms import layout as crispy
from crispy_forms.layout import Submit

from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.hqwebapp.crispy import HQFormHelper
from corehq.sql_db.util import get_db_aliases_for_partitioned_query
from custom.icds.data_management.base import SQLBasedDataManagement
from custom.icds.data_management.const import DATA_MANAGEMENT_TASKS
from custom.icds.data_management.tasks import execute_data_management


class DataManagementForm(forms.Form):
    slug = forms.ChoiceField(label=ugettext_lazy("Data Management"), choices=(
        (pull.slug, pull.name) for pull in DATA_MANAGEMENT_TASKS.values()
    ))
    db_alias = forms.ChoiceField(label=ugettext_lazy("DB partition"), choices=(
        (db_alias, db_alias) for db_alias in get_db_aliases_for_partitioned_query()
    ))
    from_date = forms.DateField(required=False, widget=forms.DateInput())
    till_date = forms.DateField(required=False, widget=forms.DateInput())

    def __init__(self, request, domain, *args, **kwargs):
        self.domain = domain
        super(DataManagementForm, self).__init__(*args, **kwargs)
        self.helper = HQFormHelper()
        self.helper.layout = crispy.Layout(
            crispy.Field('slug'),
            crispy.Field('db_alias'),
            crispy.Field('from_date', id="from_date_select", css_class="date-picker"),
            crispy.Field('till_date', id="till_date_select", css_class="date-picker"),
            hqcrispy.FormActions(
                crispy.ButtonHolder(
                    Submit('submit', ugettext_lazy("Submit"))
                )
            )
        )

    def clean_from_date(self):
        from_date = self.cleaned_data['from_date']
        slug = self.cleaned_data['slug']
        if not from_date and issubclass(DATA_MANAGEMENT_TASKS[slug], SQLBasedDataManagement):
            self.add_error("from_date", "From date needed to run SQL based tasks")
        return from_date

    def clean(self):
        from_date = self.cleaned_data['from_date']
        till_date = self.cleaned_data['till_date']
        if from_date and till_date and from_date < till_date:
            self.add_error("till_date", "Till date should be greater than from date")

    def submit(self, domain, username):
        execute_data_management.delay(
            self.cleaned_data['slug'],
            domain,
            self.cleaned_data['db_alias'],
            username,
            self.cleaned_data['from_date'],
            self.cleaned_data['till_date']
        )
