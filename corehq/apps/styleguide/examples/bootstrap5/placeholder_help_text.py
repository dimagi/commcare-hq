from django import forms
from django.utils.translation import gettext_lazy

from crispy_forms import layout as crispy

from corehq.apps.hqwebapp import crispy as hqcrispy


class PlaceholderHelpTextExampleForm(forms.Form):
    """
    This example demonstrates the use of placeholders
    and help text in Crispy Forms
    """
    email = forms.EmailField(
        label=gettext_lazy("Email"),
        # note that the help_text is set here
        help_text=gettext_lazy("We'll never share your email with anyone else."),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = hqcrispy.HQFormHelper()
        self.helper.layout = crispy.Layout(
            crispy.Field('email', placeholder="name@example.com"),
        )
