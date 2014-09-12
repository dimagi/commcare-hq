from django import forms
from django.utils.translation import ugettext as _
from bootstrap3_crispy.helper import FormHelper
from bootstrap3_crispy.layout import Submit
from corehq.apps.userreports.ui.fields import ReportDataSourceField, JsonField
forms.ModelForm


class DocumentFormBase(forms.Form):
    """
    HQ specific document base form. Loosely modeled off of Django's ModelForm
    """

    def __init__(self, instance=None, *args, **kwargs):
        self.instance = instance
        object_data = instance._doc if instance is not None else {}
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', _('Save Changes')))
        super(DocumentFormBase, self).__init__(initial=object_data, *args, **kwargs)

    def save(self, commit=False):
        for field in self.fields:
            setattr(self.instance, field, self.cleaned_data[field])
        if commit:
            self.instance.save()
        return self.instance


class ConfigurableReportEditForm(DocumentFormBase):

    config_id = forms.ChoiceField()  # gets overridden on instantiation
    display_name = forms.CharField()
    description = forms.CharField(required=False)
    aggregation_columns = JsonField()
    filters = JsonField()
    columns = JsonField()

    def __init__(self, domain, instance=None, *args, **kwargs):
        super(ConfigurableReportEditForm, self).__init__(instance, *args, **kwargs)
        self.fields['config_id'] = ReportDataSourceField(domain=domain)
