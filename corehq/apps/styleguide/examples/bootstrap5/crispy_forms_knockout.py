from django import forms
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy

from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.hqwebapp.widgets import BootstrapSwitchInput


class KnockoutCrispyExampleForm(forms.Form):
    """
    This is an example form that demonstrates the use
    of Crispy Forms in HQ with Knockout JS
    """
    full_name = forms.CharField(
        label=gettext_lazy("Full Name"),
    )
    area = forms.ChoiceField(
        label=gettext_lazy("Area"),
        required=False,
    )
    include_message = forms.BooleanField(
        label=gettext_lazy("Options"),
        widget=BootstrapSwitchInput(
            inline_label=gettext_lazy(
                "include message"
            ),
            # note that some widgets prefer to set data-bind attributes
            # this way, otherwise the formatting looks off:
            attrs={"data-bind": "checked: includeMessage"},
        ),
        required=False,
    )
    message = forms.CharField(
        label=gettext_lazy("Message"),
        widget=forms.Textarea(attrs={"class": "vertical-resize"}),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = hqcrispy.HQFormHelper()

        self.helper.form_id = "ko-example-crispy-form"
        self.helper.attrs.update({
            # we can capture the submit action with a data-bind here:
            "data-bind": "submit: onFormSubmit",
        })

        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("Report an Issue"),
                crispy.Div(
                    # It's also possible to use crispy.HTML
                    # instead of crispy.Div, but make sure any HTMl
                    # inserted here is safe
                    crispy.Div(
                        '',
                        css_class="alert alert-info",
                        # data-bind to display alertText
                        data_bind="text: alertText",
                    ),
                    # data-bind to toggle visibility
                    data_bind="visible: alertText()"
                ),
                crispy.Field(
                    'full_name',
                    # data-bind applying value of input to fullName
                    data_bind="value: fullName"
                ),
                crispy.Field(
                    'area',
                    # data-bind creating select2 (see Molecules > Selections)
                    data_bind="select2: areas, value: area"
                ),
                twbscrispy.PrependedText('include_message', ''),
                crispy.Div(
                    crispy.Field('message', data_bind="value: message"),
                    # we apply a data-bind on the visibility to a wrapper
                    # crispy.Div, otherwise only the textarea visibility
                    # is toggled, while the label remains
                    data_bind="visible: includeMessage",
                ),

            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _("Submit Report"),
                    type="submit",
                    css_class="btn btn-primary",
                ),
                twbscrispy.StrictButton(
                    _("Cancel"),
                    css_class="btn btn-outline-primary",
                    # data-bind on the click event of the Cancel button
                    data_bind="click: cancelSubmission",
                ),
            ),
        )
