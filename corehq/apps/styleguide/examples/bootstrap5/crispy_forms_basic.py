from django import forms
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy

from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.hqwebapp.widgets import BootstrapCheckboxInput


class BasicCrispyExampleForm(forms.Form):
    """
    This is a basic example form that demonstrates
    the use of Crispy Forms in HQ.
    """
    full_name = forms.CharField(
        label=gettext_lazy("Full Name"),
    )
    message = forms.CharField(
        label=gettext_lazy("Message"),
        widget=forms.Textarea(attrs={"class": "vertical-resize"}),
    )
    forward_message = forms.BooleanField(
        label=gettext_lazy("Forward Message"),
        required=False,
        widget=BootstrapCheckboxInput(
            inline_label=gettext_lazy(
                "Yes, forward this message to me."
            ),
        ),
    )
    language = forms.ChoiceField(
        label=gettext_lazy("Language"),
        choices=(
            ('en', gettext_lazy("English")),
            ('fr', gettext_lazy("French")),
            ('es', gettext_lazy("Spanish")),
            ('de', gettext_lazy("German")),
        ),
        required=False,
    )
    language_test_status = forms.BooleanField(
        label=gettext_lazy("Include me in language tests"),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Here's what makes the form a Crispy Form
        self.helper = hqcrispy.HQFormHelper()

        # This is the layout of the form where we can explicitly specify the
        # order of fields and group fields into fieldsets:
        self.helper.layout = crispy.Layout(

            crispy.Fieldset(
                # This is the title for the group of fields that follows:
                _("Basic Information"),

                # By default, specifying a string with the field's slug
                # invokes crispy.Field as the default display component
                'full_name',

                # This line is effectively the same as the line above
                # and useful for adding attributes:
                crispy.Field('message'),

                # This is a special component that is best to use
                # in combination with BootstrapCheckboxInput on a
                # BooleanField (see Molecules > Checkboxes)
                twbscrispy.PrependedText('forward_message', ''),
            ),
            crispy.Fieldset(
                _("Advanced Information"),
                'language',
                'language_test_status',
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _("Send Message"),
                    type="submit",
                    css_class="btn btn-primary",
                ),
                hqcrispy.LinkButton(  # can also be a StrictButton
                    _("Cancel"),
                    '#',
                    css_class="btn btn-outline-primary",
                ),
            ),
        )
