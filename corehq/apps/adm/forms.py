from django import forms
from django.forms.util import ErrorList
from django.forms.widgets import Textarea
from corehq.apps.adm.models import ADMColumn, ReducedADMColumn, DaysSinceADMColumn, ConfigurableADMColumn, \
    InactiveADMColumn, ADMCompareColumn, ADMReport, KEY_TYPE_OPTIONS, REPORT_SECTION_OPTIONS
from dimagi.utils.data.editable_items import InterfaceEditableItemForm

class UpdateADMItemForm(InterfaceEditableItemForm):
    name = forms.CharField(label="Name")
    description = forms.CharField(label="Description", required=False,
        widget=Textarea(attrs=dict(style="height:80px;width:340px;")))

class UpdateADMColumnForm(UpdateADMItemForm):
    couch_view = forms.CharField(label="Couch View")
    key_format = forms.CharField(label="Key Format",
        help_text="keywords are <domain>, <user_id>, and <datespan>",
        widget=forms.TextInput(attrs=dict(placeholder="ex: <domain>, <user_id>, <datespan>"))
    )

    _item_class = ADMColumn

class UpdateReducedADMColumnForm(UpdateADMColumnForm):
    returns_numerical = forms.BooleanField(label="Returns a Number", initial=False, required=False,
        help_text="This view returns a number.")
    duration_of_project = forms.BooleanField(label="Return All Records", initial=False, required=False,
        help_text="If unchecked, the records returned will be between the startdate and enddate of the datespan.")

    _item_class = ReducedADMColumn

DATESPAN_CHOICES = [("startdate", "Start of Datespan"), ("enddate", "End of Datespan")]

class DaysSinceADMColumnForm(UpdateADMColumnForm):
    property_name = forms.CharField(label="Property Name",
        help_text="Must be a property of type datetime."
    )
    start_or_end = forms.CharField(label="Days Between Property and",
        widget=forms.Select(choices=DATESPAN_CHOICES)
    )

    _item_class = DaysSinceADMColumn

class ConfigurableADMColumnForm(InterfaceEditableItemForm):
    column_type = forms.CharField(label="Column Type",
        widget=forms.Select(choices=[("", "Select a column type...")]+[(c.__name__, c.__name__)
        for c in ConfigurableADMColumn.__subclasses__()])
    )

    _item_class = ConfigurableADMColumn

    def __init__(self, data=None, files=None, auto_id='id_%s', prefix=None,
                 initial=None, error_class=ErrorList, label_suffix=':',
                 empty_permitted=False, item_id=None):

        super(ConfigurableADMColumnForm, self).__init__(data, files, auto_id, prefix, initial, error_class,
            label_suffix, empty_permitted, item_id)

    def save(self):
        pass

    def update(self, item):
        pass

class InactiveADMColumnForm(UpdateADMColumnForm):
    directly_configurable = forms.BooleanField(label="Directly Configurable",
        initial=True,
        required=False,
        help_text="This column can be directly configured by the user."
    )
    inactivity_milestone = forms.IntegerField(label="Inactivity Milestone", initial=0,
        help_text="The number of days that must pass for a case to be marked as inactive."
    )

    _item_class = InactiveADMColumn


class ADMCompareColumnForm(UpdateADMItemForm):
    directly_configurable = forms.BooleanField(label="Directly Configurable",
        initial=False,
        required=False,
        help_text="This column can be directly configured by the user."
    ) #yeah, sorry. I got lazy.
    numerator_id = forms.CharField(label="Numerator",
        widget=forms.Select(choices=ADMCompareColumn.numerical_column_options())
    )
    denominator_id = forms.CharField(label="Denominator",
        widget=forms.Select(choices=ADMCompareColumn.numerical_column_options())
    )

    _item_class = ADMCompareColumn


class ADMReportForm(UpdateADMItemForm):
    slug = forms.SlugField(label="Slug")
    reporting_section = forms.CharField(label="Reporting Section",
        widget=forms.Select(choices=REPORT_SECTION_OPTIONS)
    )
    column_list = forms.CharField(label="Column IDs",
        help_text="A comma separated list of column ids for the report.",
        required=False,
        widget=Textarea(attrs=dict(style="height:80px;width:340px;"))
    )
    key_type = forms.CharField(label="Key By",
        widget=forms.Select(choices=KEY_TYPE_OPTIONS)
    )

    _item_class = ADMReport

    def __init__(self, data=None, files=None, auto_id='id_%s', prefix=None,
                 initial=None, error_class=ErrorList, label_suffix=':',
                 empty_permitted=False, item_id=None):
        if data and "column_list" not in data:
            copied_data = data.copy()
            cols = data.get("column_ids", [])
            copied_data["column_list"] = ",".join(cols)
            data = copied_data
        super(ADMReportForm, self).__init__(data, files, auto_id, prefix, initial, error_class,
            label_suffix, empty_permitted, item_id)

    def clean_column_list(self):
        cols = self.cleaned_data["column_list"]
        return [c.strip() for c in cols.split(',')] if cols else []