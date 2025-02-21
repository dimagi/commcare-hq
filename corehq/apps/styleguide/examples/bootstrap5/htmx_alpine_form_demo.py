import json

from crispy_forms import bootstrap as twbscrispy, layout as crispy
from crispy_forms.helper import FormHelper

from django import forms
from django.utils.translation import gettext_lazy, gettext as _


class MatchType:
    EXACT = "exact"
    IS_NOT = "is_not"
    CONTAINS = "contains"
    IS_EMPTY = "is_empty"

    OPTIONS = (
        (EXACT, gettext_lazy("is exactly")),
        (IS_NOT, gettext_lazy("is not")),
        (CONTAINS, gettext_lazy("contains")),
        (IS_EMPTY, gettext_lazy("is empty")),
    )

    MATCHES_WITH_VALUES = (
        EXACT, IS_NOT, CONTAINS,
    )


class FilterDemoForm(forms.Form):
    slug = forms.ChoiceField(
        label=gettext_lazy("Column"),
        choices=(
            ('name', gettext_lazy("Name")),
            ('color', gettext_lazy("Color")),
            ('desc', gettext_lazy("Description")),
        ),
        required=False
    )
    match = forms.ChoiceField(
        label=gettext_lazy("Match Type"),
        choices=MatchType.OPTIONS,
        required=False,
        help_text=gettext_lazy(
            "Hint: select 'is empty' to watch the Value field below disappear"
        )
    )
    value = forms.CharField(
        label=gettext_lazy("Value"),
        strip=False,
        required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()

        # We defer to defining the <form> tag in the template as we will
        # use HTMX to load and submit the form. Keeping the HTMX attributes
        # local to the template is preferred to maintain context.
        self.helper.form_tag = False

        # This form layout uses Alpine to toggle the visibility of
        # the "value" field:
        self.helper.layout = crispy.Layout(
            crispy.Div(
                'slug',
                crispy.Field(
                    'match',
                    # We initialize the match value in the alpine
                    # model defined below:
                    x_init="match = $el.value",
                    # and then two-way bind the alpine match
                    # model variable to this input:
                    x_model="match",
                ),
                crispy.Div(
                    'value',
                    # This uses alpine to determine whether to
                    # show the value field, based on the valueMatches
                    # list defined in the alpine model below:
                    x_show="valueMatches.includes(match)",
                ),
                twbscrispy.StrictButton(
                    _("Add Filter"),
                    type="submit",
                    css_class="btn btn-primary",
                ),
                # The Alpine data model is easily bound to the form
                # to control hiding/showing the value field:
                x_data=json.dumps({
                    "match": self.fields['match'].initial,
                    "valueMatches": MatchType.MATCHES_WITH_VALUES,
                }),
            ),
        )

    def clean(self):
        match = self.cleaned_data['match']
        value = self.cleaned_data['value']
        if match in MatchType.MATCHES_WITH_VALUES and not value:
            self.add_error('value', _("Please specify a value."))
