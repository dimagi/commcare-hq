from django import forms
from django.utils.translation import gettext as _, gettext_lazy

from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy
from crispy_forms.helper import FormHelper

from corehq.apps.prototype.models.data_cleaning.filters import ColumnMatchType, ColumnFilter


class AddColumnFilterForm(forms.Form):
    slug = forms.ChoiceField(
        label=gettext_lazy("Column"),
        choices=(),
    )
    match = forms.ChoiceField(
        label=gettext_lazy("Match Type"),
        choices=ColumnMatchType.OPTIONS,
    )
    value = forms.CharField(
        label=gettext_lazy("Value"),
    )

    def __init__(self, table_config, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].choices = [
            (c[0], c[1].verbose_name)
            for c in table_config.available_columns
        ]

        self.helper = FormHelper()
        self.helper.layout = crispy.Layout(
            'slug',
            'match',
            'value',
            twbscrispy.StrictButton(
                _("Add Filter"),
                type="submit",
                css_class="btn-primary",
            ),
        )

    def add_filter(self, request):
        ColumnFilter.add_filter(
            request,
            self.cleaned_data['slug'],
            self.cleaned_data['match'],
            self.cleaned_data['value'],
        )
