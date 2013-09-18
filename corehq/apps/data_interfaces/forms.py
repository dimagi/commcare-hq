from crispy_forms.bootstrap import StrictButton, InlineField, FormActions
from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field, HTML, Div
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _, ugettext_noop


class AddCaseGroupForm(forms.Form):
    name = forms.CharField(required=True, label=ugettext_noop("Group Name"))

    def __init__(self, *args, **kwargs):
        super(AddCaseGroupForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_style = 'inline'
        self.helper.form_show_labels = False
        self.helper.layout = Layout(
            InlineField('name'),
            StrictButton(
                mark_safe('<i class="icon-plus"></i> %s' % _("Create Group")),
                css_class='btn-success',
                type="submit"
            )
        )


class UpdateCaseGroupForm(AddCaseGroupForm):
    item_id = forms.HiddenInput()

    def __init__(self, *args, **kwargs):
        super(UpdateCaseGroupForm, self).__init__(*args, **kwargs)
        self.helper.form_style = 'default'
        self.helper.form_show_labels = True
        self.helper.layout = Layout(
            InlineField('item_id'),
            Div(
                Field('name'),
                css_class='modal-body'
            ),
            FormActions(
                StrictButton(
                    _("Update Group"),
                    css_class='btn-primary',
                    type="submit",

                ),
                HTML('<button type="button" class="btn" data-dismiss="modal">Cancel</button>'),
                css_class='modal-footer'
            )

        )
