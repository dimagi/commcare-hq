from django import forms
from django.forms.util import ErrorList
from django.forms.widgets import Textarea
from django.utils.safestring import mark_safe
from corehq.apps.adm.models import BaseADMColumn, ReducedADMColumn, DaysSinceADMColumn, ConfigurableADMColumn,\
    CompareADMColumn, ADMReport, KEY_TYPE_OPTIONS, REPORT_SECTION_OPTIONS, \
    CASE_FILTER_OPTIONS, CASE_STATUS_OPTIONS, CaseCountADMColumn, ConfigurableADMColumn, CouchViewADMColumn, SORT_BY_DIRECTION_OPTIONS, UserDataADMColumn
from corehq.apps.crud.models import BaseAdminCRUDForm
from hqstyle.forms import fields as hq_fields
from dimagi.utils.data.crud import BaseCRUDForm

DATESPAN_CHOICES = [("startdate", "Start of Datespan"), ("enddate", "End of Datespan")]
IGNORE_DATESPAN_FIELD = forms.BooleanField(
    label="Ignore Datespan and Return All Records",
    initial=False,
    required=False,
    help_text="If unchecked, the records returned will be between the startdate and enddate of the datespan."
)

class BaseADMDocumentForm(BaseAdminCRUDForm):
    slug = forms.SlugField(label="Slug")
    domain = forms.CharField(label="Project Name (blank applies to all projects)", required=False)
    name = forms.CharField(label="Name")
    description = forms.CharField(label="Description", required=False,
        widget=Textarea(attrs=dict(style="height:80px;width:340px;")))


class CouchViewADMColumnForm(BaseADMDocumentForm):
    doc_class = CouchViewADMColumn
    couch_view = forms.CharField(label="Couch View")
    key_format = forms.CharField(label="Key Format",
        help_text="keywords are <domain>, <user_id>, and <datespan>",
        widget=forms.TextInput(attrs=dict(placeholder="ex: <domain>, <user_id>, <datespan>"))
    )


class ReducedADMColumnForm(CouchViewADMColumnForm):
    doc_class = ReducedADMColumn
    returns_numerical = forms.BooleanField(label="Returns a Number", initial=False, required=False,
        help_text="This view returns a number.")
    ignore_datespan = IGNORE_DATESPAN_FIELD


class DaysSinceADMColumnForm(CouchViewADMColumnForm):
    doc_class = DaysSinceADMColumn
    property_name = forms.CharField(label="Property Name",
        help_text="Must be a property of type datetime."
    )
    start_or_end = forms.CharField(label="Days Between Property and",
        widget=forms.Select(choices=DATESPAN_CHOICES)
    )


class ConfigurableADMColumnChoiceForm(BaseCRUDForm):
    """
        This form provides a way to choose which configurable column type you want to edit.
    """
    column_choice = forms.CharField(label="Column Type")
    doc_class = ConfigurableADMColumn

    def __init__(self, data=None, files=None, auto_id='id_%s', prefix=None,
                 initial=None, error_class=ErrorList, label_suffix=':',
                 empty_permitted=False, doc_id=None):
        super(ConfigurableADMColumnChoiceForm, self).__init__(data, files, auto_id, prefix, initial, error_class,
            label_suffix, empty_permitted, doc_id)
        self.fields['column_choice'].widget = forms.Select(
                choices=[("", "Select a column type...")]+[(c.__name__, c.column_type())
                        for c in ConfigurableADMColumn.__subclasses__()]
            )

    def save(self):
        pass


class ConfigurableADMColumnForm(BaseADMDocumentForm):
    is_configurable = forms.BooleanField(label="Configurable",
        initial=True,
        required=False,
        help_text="This column can be directly configured by a user."
    )


class CaseFilterFormMixin(forms.Form):
    filter_option = forms.CharField("Filter Option",
        required=False,
        widget=forms.Select(choices=CASE_FILTER_OPTIONS))
    case_types = hq_fields.CSVListField("Case Types",
        required=False,
        help_text="Please provide a comma-separated list of case types.")
    case_status = forms.CharField("Case Status",
        required=False,
        widget=forms.Select(choices=CASE_STATUS_OPTIONS))

class UserDataADMColumnForm(ConfigurableADMColumnForm):
    doc_class = UserDataADMColumn
    user_data_key = forms.CharField(label="User Data Key")


class CaseCountADMColumnForm(ConfigurableADMColumnForm, CaseFilterFormMixin):
    doc_class = CaseCountADMColumn
    inactivity_milestone = forms.IntegerField(label="Inactivity Milestone", initial=0,
        help_text=mark_safe("The number of days that must pass for a case to be marked as inactive. <br />"
                            "In general, if this option is > 0, this column will return a count of cases "
                            "in the date span of [beginning of time] to [enddate - inactivity_milestone(days)]"),
        required=False
    )
    ignore_datespan = forms.BooleanField(label="Ignore Datespan",
        initial=True,
        required=False,
        help_text=mark_safe("If this option is checked, this will return a count of cases over all time. "
                            "(Cases are sorted by date_modified) <br />"
                            "Note: If inactivity milestone is > 0 days, this option is is not used."))

    def __init__(self, data=None, files=None, auto_id='id_%s', prefix=None,
                 initial=None, error_class=ErrorList, label_suffix=':',
                 empty_permitted=False, doc_id=None):
        super(CaseCountADMColumnForm, self).__init__(data, files, auto_id, prefix, initial, error_class,
            label_suffix, empty_permitted, doc_id)
        self.fields['case_status'].help_text = "If you use 'Inactivity Milestone' below, you likely " \
                                                "want to select only 'Open Cases'."


    def clean(self):
        cleaned_data = super(CaseCountADMColumnForm, self).clean()
        case_types = cleaned_data.get('case_types', [])
        filter_option = cleaned_data.get('filter_option', '')
        if filter_option == '' and len(case_types) > 0 and case_types[0]:
            raise forms.ValidationError('You specified a list of case types, but you did not choose how to filter them.')
        if filter_option == 'in' and len(case_types) == 0:
            raise forms.ValidationError('You did not specify any case types to filter by. No cases will be counted.')
        return cleaned_data


class CompareADMColumnForm(ConfigurableADMColumnForm):
    doc_class = CompareADMColumn
    numerator_ref = forms.CharField(label="Numerator")
    denominator_ref = forms.CharField(label="Denominator")

    def __init__(self, data=None, files=None, auto_id='id_%s', prefix=None,
                 initial=None, error_class=ErrorList, label_suffix=':',
                 empty_permitted=False, doc_id=None):
        super(CompareADMColumnForm, self).__init__(data, files, auto_id, prefix, initial, error_class,
            label_suffix, empty_permitted, doc_id)
        self.fields['numerator_ref'].widget = forms.Select(choices=CompareADMColumn.default_numerical_column_options())
        self.fields['denominator_ref'].widget = forms.Select(choices=CompareADMColumn.default_numerical_column_options())
        self.fields['is_configurable'].initial = False


class ADMReportForm(BaseADMDocumentForm):
    doc_class = ADMReport
    reporting_section = forms.CharField(label="Reporting Section",
        widget=forms.Select(choices=REPORT_SECTION_OPTIONS)
    )
    column_refs = hq_fields.CSVListField(label="Column Slugs",
        help_text="A comma separated list of column slugs for the report.",
        required=False,
        widget=Textarea(attrs=dict(style="height:80px;width:340px;"))
    )
    sort_by_default = forms.CharField(label="Slug of Sort By Default",
        required=False,
        help_text="The default is to sort by username.")
    sort_by_direction = forms.CharField(label="Sort By Direction",
        widget=forms.Select(choices=SORT_BY_DIRECTION_OPTIONS)
    )
    key_type = forms.CharField(label="Key By",
        widget=forms.Select(choices=KEY_TYPE_OPTIONS)
    )
