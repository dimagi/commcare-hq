from django import forms
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy

from corehq.apps.hqwebapp import crispy as hqcrispy


class BasicCrispyForm(forms.Form):
    first_name = forms.CharField(
        label=gettext_lazy("First Name"),
    )
    favorite_color = forms.ChoiceField(
        label=gettext_lazy("Pick a Favorite Color"),
        choices=(
            ('red', gettext_lazy("Red")),
            ('green', gettext_lazy("Green")),
            ('blue', gettext_lazy("Blue")),
            ('purple', gettext_lazy("Purple")),
        ),
    )

    def __init__(self, *args, **kwargs):
        super(BasicCrispyForm, self).__init__(*args, **kwargs)
        self.helper = hqcrispy.HQFormHelper()

        self.helper.form_method = 'POST'
        self.helper.form_action = '#'

        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("Basic Information"),
                crispy.Field('first_name'),
                crispy.Field('favorite_color'),
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _("Save"),
                    type="submit",
                    css_class="btn btn-primary",
                ),
                hqcrispy.LinkButton(
                    _("Cancel"),
                    '#',
                    css_class="btn btn-default",
                ),
            ),
        )


class CheckboxesForm(forms.Form):
    send_email = forms.BooleanField(
        label=gettext_lazy("This checkbox is badly aligned"),
        required=False,
    )
    recipient = forms.CharField(
        label=gettext_lazy("Email recipient"),
    )
    send_to_self = forms.BooleanField(
        label=gettext_lazy("Also send to myself"),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super(CheckboxesForm, self).__init__(*args, **kwargs)
        self.helper = hqcrispy.HQFormHelper()

        self.helper.form_method = 'POST'
        self.helper.form_action = '#'

        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("Basic Information"),
                hqcrispy.B3MultiField(
                    _("Send email when complete"),
                    "send_email",
                ),
                crispy.Field('recipient'),
                crispy.Field('send_to_self'),
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _("Save"),
                    type="submit",
                    css_class="btn btn-primary",
                ),
                hqcrispy.LinkButton(
                    _("Cancel"),
                    '#',
                    css_class="btn btn-default",
                ),
            ),
        )
