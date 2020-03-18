from django import forms
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy

from crispy_forms import layout as crispy
from crispy_forms.bootstrap import StrictButton

from corehq.apps.hqwebapp.crispy import HQFormHelper
from corehq.apps.locations.models import LocationType
from corehq.util.workbook_json.excel import get_workbook


class LocationRationalizationTemplateForm(forms.Form):
    location_id = forms.CharField(label=ugettext_lazy("Location"), widget=forms.widgets.Select(choices=[]),
                                  required=True)
    location_type = forms.ChoiceField(label=ugettext_lazy("Location Type"), choices=(), required=True,
                                      help_text=_("the location type each row should represent in download"
                                                  " or ideally the smallest possible location type"))

    def __init__(self, domain, *args, **kwargs):
        self.domain = domain
        super(LocationRationalizationTemplateForm, self).__init__(*args, **kwargs)
        self.fields['location_type'].choices = self._location_type_choices()
        self.helper = HQFormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = crispy.Layout(
            crispy.Field('location_id', id='location_search_select'),
            crispy.Field('location_type'),
            StrictButton(ugettext_lazy('Download'), css_class='btn-primary', type='submit'),
        )
        self.location_id = None

    def _location_type_choices(self):
        return [(loc_type.code, loc_type.name)
                for loc_type in LocationType.objects.by_domain(self.domain)]
