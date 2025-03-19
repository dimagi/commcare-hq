from django import forms
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from crispy_forms import layout as crispy

from corehq.apps.hqwebapp import crispy as hqcrispy


class DisabledFieldsExampleForm(forms.Form):
    """
    This is example demonstrates the use of
    disabled and readonly plaintext fields
    in Crispy Forms.
    """
    # NOTE the _dis and _ro in the field slugs are just to differentiate similar fields and not part of convention
    full_name_dis = forms.CharField(
        label=gettext_lazy("Full Name"),
    )
    message_dis = forms.CharField(
        label=gettext_lazy("Message"),
        widget=forms.Textarea(),
    )
    full_name_ro = forms.CharField(
        label=gettext_lazy("Full Name"),
    )
    message_ro = forms.CharField(
        label=gettext_lazy("Message"),
        widget=forms.Textarea(),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Sets up initial data. You may also pass a dictionary to the initial kwarg when initializing the form.
        self.fields['full_name_dis'].initial = "Jon Jackson"
        self.fields['message_dis'].initial = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. " \
                                             "Fusce in facilisis lectus. Cras accumsan ante vel massa " \
                                             "sagittis faucibus."
        self.fields['full_name_ro'].initial = "Jon Jackson"
        self.fields['message_ro'].initial = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. " \
                                            "Fusce in facilisis lectus. Cras accumsan ante vel massa " \
                                            "sagittis faucibus."

        self.helper = hqcrispy.HQFormHelper()
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("Examples of Disabled Fields"),
                # note the disabled attribute
                crispy.Field('full_name_dis', disabled=""),
                crispy.Field('message_dis', disabled=""),
            ),
            crispy.Fieldset(
                _("Examples of Readonly Fields"),
                # note the disabled attribute and
                # form-control-plaintext css_class
                crispy.Field(
                    'full_name_ro',
                    readonly="",
                    css_class="form-control-plaintext"
                ),
                crispy.Field(
                    'message_ro',
                    readonly="",
                    css_class="form-control-plaintext"
                ),
            ),
        )
