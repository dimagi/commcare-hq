from django.utils.translation import ugettext_lazy, ugettext as _
from django.forms.forms import Form
from django.forms.fields import CharField, ChoiceField

from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy

from corehq.apps.hqwebapp import crispy as hqcrispy


class BulkActionForm(Form):
    domain = None
    name = CharField(
        label=ugettext_lazy("Name")
    )
    action_type = ChoiceField(
        choices=[('Simple', 'Simple'), ('Form', 'Form')],
        label=ugettext_lazy("Type")
    )

    def __init__(self, *args, **kwargs):
        super(BulkActionForm, self).__init__(*args, **kwargs)
        self.helper = hqcrispy.HQFormHelper()

        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("Bulk Action"),
                crispy.Field('name'),
                crispy.Field('action_type'),
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

