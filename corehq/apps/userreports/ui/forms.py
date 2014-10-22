from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _
from bootstrap3_crispy.helper import FormHelper
from bootstrap3_crispy.layout import Submit
from corehq.apps.userreports.ui.fields import ReportDataSourceField, JsonField


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
        self.populate_instance(self.instance, self.cleaned_data)
        if commit:
            self.instance.save()
        return self.instance

    def populate_instance(self, instance, cleaned_data):
        for field in self.fields:
            setattr(instance, field, cleaned_data[field])
        return instance


class ConfigurableReportEditForm(DocumentFormBase):

    config_id = forms.ChoiceField()  # gets overridden on instantiation
    title = forms.CharField()
    description = forms.CharField(required=False)
    aggregation_columns = JsonField(expected_type=list)
    filters = JsonField(expected_type=list)
    columns = JsonField(expected_type=list)
    configured_charts = JsonField(expected_type=list)

    def __init__(self, domain, instance=None, *args, **kwargs):
        super(ConfigurableReportEditForm, self).__init__(instance, *args, **kwargs)
        self.fields['config_id'] = ReportDataSourceField(domain=domain)

    def clean(self):
        cleaned_data = super(ConfigurableReportEditForm, self).clean()
        # only call additional validation if initial validation has passed for all fields
        for field in self.fields:
            if field not in cleaned_data:
                return
        try:
            config = self.populate_instance(self.instance, cleaned_data)
            config.validate()
        except Exception, e:
            raise ValidationError(_(u'Problem with report spec: {}').format(e))
        return cleaned_data


DOC_TYPE_CHOICES = (
    ('CommCareCase', 'cases'),
    ('XFormInstance', 'forms')
)


class ConfigurableDataSourceEditForm(DocumentFormBase):

    table_id = forms.CharField()
    referenced_doc_type = forms.ChoiceField(choices=DOC_TYPE_CHOICES)
    display_name = forms.CharField()
    description = forms.CharField(required=False)
    configured_filter = JsonField(expected_type=dict)
    configured_indicators = JsonField(expected_type=list)

    def clean(self):
        cleaned_data = super(ConfigurableDataSourceEditForm, self).clean()
        # only call additional validation if initial validation has passed for all fields
        for field in self.fields:
            if field not in cleaned_data:
                return
        try:
            config = self.populate_instance(self.instance, cleaned_data)
            config.validate()
        except Exception, e:
            raise ValidationError(_(u'Problem with data source spec: {}').format(e))
        return cleaned_data
