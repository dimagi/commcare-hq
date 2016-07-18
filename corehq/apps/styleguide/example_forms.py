from django import forms
from django.utils.translation import ugettext_lazy, ugettext as _
from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy
from crispy_forms import bootstrap as twbscrispy
from corehq.apps.style import crispy as hqcrispy


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
        self.helper = FormHelper()

        self.helper.form_method = 'POST'
        self.helper.form_class = 'form-horizontal'
        self.helper.form_action = '#'

        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'

        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("Basic Information"),
                crispy.Field('first_name'),
                crispy.Field('favorite_color'),
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _("Submit Information"),
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
