from django import forms
from django.forms.widgets import Textarea
from corehq.apps.adm.models import ADMColumn, ReducedADMColumn, DaysSinceADMColumn
from dimagi.utils.data.editable_items import InterfaceEditableItemForm

class UpdateADMColumnForm(InterfaceEditableItemForm):
    name = forms.CharField(label="Column Name")
    description = forms.CharField(label="Description", required=False, widget=Textarea)
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