from django import forms
from django.forms.util import ErrorList
from django.forms.widgets import Textarea
from corehq.apps.adm.models import ADMColumn, ReducedADMColumn, DaysSinceADMColumn, ConfigurableADMColumn, \
    ADMCompareColumn, ADMReport, KEY_TYPE_OPTIONS, REPORT_SECTION_OPTIONS, \
    CASE_FILTER_OPTIONS, CASE_STATUS_OPTIONS, CaseCountADMColumn
from corehq.apps.hq_bootstrap.forms import fields as hq_fields
from dimagi.utils.data.editable_items import InterfaceEditableItemForm

DATESPAN_CHOICES = [("startdate", "Start of Datespan"), ("enddate", "End of Datespan")]

IGNORE_DATESPAN_FIELD = forms.BooleanField(label="Ignore Datespan and Return All Records", initial=False, required=False,
    help_text="If unchecked, the records returned will be between the startdate and enddate of the datespan.")


class UpdateADMItemForm(InterfaceEditableItemForm):
    name = forms.CharField(label="Name")
    description = forms.CharField(label="Description", required=False,
        widget=Textarea(attrs=dict(style="height:80px;width:340px;")))
    slug = forms.SlugField(label="Slug")


class UpdateCouchViewADMColumnForm(UpdateADMItemForm):
    couch_view = forms.CharField(label="Couch View")
    key_format = forms.CharField(label="Key Format",
        help_text="keywords are <domain>, <user_id>, and <datespan>",
        widget=forms.TextInput(attrs=dict(placeholder="ex: <domain>, <user_id>, <datespan>"))
    )

    _item_class = ADMColumn


class UpdateReducedADMColumnForm(UpdateCouchViewADMColumnForm):
    returns_numerical = forms.BooleanField(label="Returns a Number", initial=False, required=False,
        help_text="This view returns a number.")
    ignore_datespan = IGNORE_DATESPAN_FIELD

    _item_class = ReducedADMColumn


class DaysSinceADMColumnForm(UpdateCouchViewADMColumnForm):
    property_name = forms.CharField(label="Property Name",
        help_text="Must be a property of type datetime."
    )
    start_or_end = forms.CharField(label="Days Between Property and",
        widget=forms.Select(choices=DATESPAN_CHOICES)
    )

    _item_class = DaysSinceADMColumn


class ConfigurableADMColumnChoiceForm(InterfaceEditableItemForm):
    """
        This form provides a way to choose which configurable column type you want to edit.
    """
    column_type = forms.CharField(label="Column Type",
        widget=forms.Select(choices=[("", "Select a column type...")]+[(c.__name__, c.__name__)
        for c in ConfigurableADMColumn.__subclasses__()])
    )

    _item_class = ConfigurableADMColumn

    def save(self):
        pass

    def update(self, item):
        pass


class ConfigurableADMColumnForm(UpdateADMItemForm):
    domain = forms.CharField(required=False, label="Project Name (blank applies to all projects)")
    directly_configurable = forms.BooleanField(label="Directly Configurable",
        initial=True,
        required=False,
        help_text="This column can be directly configured by the user."
    )


class CaseFilterADMColumnFormMixin(forms.Form):
    filter_option = forms.CharField("Filter Option",
        required=False,
        widget=forms.Select(choices=CASE_FILTER_OPTIONS))
    case_types = hq_fields.CSVListField("Case Types",
        required=False,
        help_text="Please provide a comma-separated list of case types.")
    case_status = forms.CharField("Case Status",
        required=False,
        widget=forms.Select(choices=CASE_STATUS_OPTIONS))


class CaseCountADMColumnForm(ConfigurableADMColumnForm, CaseFilterADMColumnFormMixin):
    inactivity_milestone = forms.IntegerField(label="Inactivity Milestone", initial=0,
        help_text="The number of days that must pass for a case to be marked as inactive.",
        required=False
    )
    ignore_datespan = forms.BooleanField(label="Ignore Datespan",
        initial=True,
        required=False,
        help_text="If inactivity milestone is > 0 days, this option is is not used. " \
            "If this option is checked, this will return a count of cases over all time.")

    _item_class = CaseCountADMColumn

    def clean_filter_option(self):
        case_types = self.cleaned_data['case_types']
        filter_option = self.cleaned_data['filter_option']
        if filter_option == '' and len(case_types) > 0:
            raise forms.ValidationError('You specified a list of case types, but you did not choose how to filter them.')
        return filter_option

    def clean_case_types(self):
        case_types = self.cleaned_data['case_types']
        filter_option = self.cleaned_data['filter_option']
        if filter_option == 'in' and len(case_types) == 0:
            raise forms.ValidationError('You did not specify any case types to filter by. No cases will be counted.')
        return case_types


class ADMCompareColumnForm(ConfigurableADMColumnForm):
    numerator_id = forms.CharField(label="Numerator")
    denominator_id = forms.CharField(label="Denominator")

    _item_class = ADMCompareColumn

    def __init__(self, data=None, files=None, auto_id='id_%s', prefix=None,
                 initial=None, error_class=ErrorList, label_suffix=':',
                 empty_permitted=False, item_id=None):
        super(ADMCompareColumnForm, self).__init__(data, files, auto_id, prefix, initial, error_class,
            label_suffix, empty_permitted, item_id)

        self.fields['numerator_id'].widget = forms.Select(choices=ADMCompareColumn.numerical_column_options())
        self.fields['denominator_id'].widget = forms.Select(choices=ADMCompareColumn.numerical_column_options())
        self.fields['directly_configurable'].initial = False


class ADMReportForm(UpdateADMItemForm):
    reporting_section = forms.CharField(label="Reporting Section",
        widget=forms.Select(choices=REPORT_SECTION_OPTIONS)
    )
    column_slugs = hq_fields.CSVListField(label="Column Slugs",
        help_text="A comma separated list of column slugs for the report.",
        required=False,
        widget=Textarea(attrs=dict(style="height:80px;width:340px;"))
    )
    key_type = forms.CharField(label="Key By",
        widget=forms.Select(choices=KEY_TYPE_OPTIONS)
    )

    _item_class = ADMReport
