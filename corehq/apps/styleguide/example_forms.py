from __future__ import absolute_import
from __future__ import unicode_literals
from django import forms
from django.utils.translation import ugettext_lazy, ugettext as _
from crispy_forms import layout as crispy
from crispy_forms import bootstrap as twbscrispy
from corehq.apps.hqwebapp import crispy as hqcrispy


class BasicCrispyForm(forms.Form):
    first_name = forms.CharField(
        label=ugettext_lazy("First Name"),
    )
    favorite_color = forms.ChoiceField(
        label=ugettext_lazy("Pick a Favorite Color"),
        choices=(
            ('red', ugettext_lazy("Red")),
            ('green', ugettext_lazy("Green")),
            ('blue', ugettext_lazy("Blue")),
            ('purple', ugettext_lazy("Purple")),
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
        label=ugettext_lazy("This checkbox is badly aligned"),
        required=False,
    )
    recipient = forms.CharField(
        label=ugettext_lazy("Email recipient"),
    )
    send_to_self = forms.BooleanField(
        label=ugettext_lazy("Also send to myself"),
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
