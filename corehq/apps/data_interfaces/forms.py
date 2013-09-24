from couchdbkit import ResourceNotFound
from crispy_forms.bootstrap import StrictButton, InlineField, FormActions
from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field, HTML, Div, Fieldset
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _, ugettext_noop
from casexml.apps.case.models import CommCareCaseGroup


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

    def create_group(self, domain):
        group = CommCareCaseGroup(
            name=self.cleaned_data['name'],
            domain=domain
        )
        group.save()
        return group


class UpdateCaseGroupForm(AddCaseGroupForm):
    item_id = forms.CharField(widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        super(UpdateCaseGroupForm, self).__init__(*args, **kwargs)
        self.helper.form_style = 'default'
        self.helper.form_show_labels = True
        self.helper.layout = Layout(
            Div(
                Field('item_id'),
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

    def clean(self):
        cleaned_data = super(UpdateCaseGroupForm, self).clean()
        try:
            self.current_group = CommCareCaseGroup.get(self.cleaned_data.get('item_id'))
        except AttributeError:
            raise forms.ValidationError("You're not passing in the group's id!")
        except ResourceNotFound:
            raise forms.ValidationError("This case group was not found in our database!")
        return cleaned_data

    def update_group(self):
        self.current_group.name = self.cleaned_data['name']
        self.current_group.save()
        return self.current_group


class AddCaseToGroupForm(forms.Form):
    case_identifier = forms.CharField(label=ugettext_noop("Case ID, External ID, or Phone Number"))

    def __init__(self, *args, **kwargs):
        super(AddCaseToGroupForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_style = 'inline'
        self.helper.form_show_labels = False
        self.helper.layout = Layout(
            InlineField(
                'case_identifier',
                css_class='input-xlarge'
            ),
            StrictButton(
                mark_safe('<i class="icon-plus"></i> %s' % _("Add Case")),
                css_class='btn-success',
                type="submit"
            )
        )


class UploadBulkCaseGroupForm(forms.Form):
    bulk_file = forms.FileField(
        label=ugettext_noop("Bulk File"),
        help_text=ugettext_noop("An excel file of case identifiers (Phone Number, External ID, or Case ID).")
    )
    action = forms.CharField(widget=forms.HiddenInput(), initial='bulk_upload')

    def __init__(self, *args, **kwargs):
        super(UploadBulkCaseGroupForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Fieldset(
                _('Upload bulk file'),
                Field('bulk_file'),
                Field('action')
            ),
            FormActions(
                StrictButton(
                    _("Upload Bulk Cases"),
                    css_class="btn-primary",
                    type="submit"
                )
            )
        )
