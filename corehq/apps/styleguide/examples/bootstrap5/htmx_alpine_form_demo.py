import json

from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy
from crispy_forms.helper import FormHelper
from django import forms
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy


class MatchType:
    EXACT = 'exact'
    IS_NOT = 'is_not'
    CONTAINS = 'contains'
    IS_EMPTY = 'is_empty'

    OPTIONS = (
        (EXACT, gettext_lazy('is exactly')),
        (IS_NOT, gettext_lazy('is not')),
        (CONTAINS, gettext_lazy('contains')),
        (IS_EMPTY, gettext_lazy('is empty')),
    )

    MATCHES_WITH_VALUES = (
        EXACT,
        IS_NOT,
        CONTAINS,
    )


class FilterDemoForm(forms.Form):
    slug = forms.ChoiceField(
        label=gettext_lazy('Column'),
        choices=(
            ('name', gettext_lazy('Name')),
            ('color', gettext_lazy('Color')),
            ('desc', gettext_lazy('Description')),
        ),
        required=False,
    )
    match = forms.ChoiceField(
        label=gettext_lazy('Match Type'),
        choices=MatchType.OPTIONS,
        required=False,
        help_text=gettext_lazy("Hint: select 'is empty' to watch the Value field below disappear"),
    )
    value = forms.CharField(label=gettext_lazy('Value'), strip=False, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()

        # We defer defining the <form> tag to the template, since we want
        # full control over the HTMX attributes (hx-post, hq-hx-action, etc.)
        # near the HTML they affect.
        self.helper.form_tag = False

        # Define the Alpine data model used by the layout below.
        # Keeping this close to the layout makes the form behavior easier to follow.
        alpine_data_model = {
            'match': self.fields['match'].initial,
            'valueMatches': MatchType.MATCHES_WITH_VALUES,
        }

        # Layout: Alpine is used to toggle visibility of the "value" field
        # based on the selected match type.
        self.helper.layout = crispy.Layout(
            crispy.Div(
                'slug',
                crispy.Field(
                    'match',
                    # Initialize the Alpine "match" variable when the field is rendered...
                    x_init='match = $el.value',
                    # ...and keep it in sync with this input via two-way binding.
                    x_model='match',
                ),
                crispy.Div(
                    'value',
                    # Only show the "value" field when the current match
                    # requires a value (defined in valueMatches).
                    x_show='valueMatches.includes(match)',
                ),
                twbscrispy.StrictButton(
                    _('Add Filter'),
                    type='submit',
                    css_class='btn btn-primary',
                ),
                # Bind the Alpine data model defined above to this wrapper <div>.
                x_data=json.dumps(alpine_data_model),
            ),
        )

    def clean(self):
        cleaned_data = super().clean()
        match = cleaned_data.get('match')
        value = cleaned_data.get('value')
        if match in MatchType.MATCHES_WITH_VALUES and not value:
            self.add_error('value', _('Please specify a value.'))
        return cleaned_data
