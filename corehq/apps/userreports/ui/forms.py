from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _
from bootstrap3_crispy.helper import FormHelper
from bootstrap3_crispy.layout import Submit
from corehq.apps.app_manager.models import Application, get_apps_in_domain, Form
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
    named_filters = JsonField(required=False, expected_type=dict,
                              label=_("Named filters (optional)"))

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


class ConfigurableDataSourceFromAppForm(forms.Form):

    app_id = forms.ChoiceField()
    case_type = forms.ChoiceField()

    def __init__(self, domain, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', _('Save Changes')))
        super(ConfigurableDataSourceFromAppForm, self).__init__(*args, **kwargs)
        apps = get_apps_in_domain(domain, full=True, include_remote=False)
        self.fields['app_id'] = forms.ChoiceField(
            label=_('Application'),
            choices=[(app._id, app.name) for app in apps]
        )
        self.fields['case_type'] = forms.ChoiceField(
            choices=[(ct, ct) for ct in set([c for app in apps for c in app.get_case_types() if c])]
        )

    def clean(self):
        cleaned_data = super(ConfigurableDataSourceFromAppForm, self).clean()
        app = Application.get(cleaned_data['app_id'])
        if cleaned_data['case_type'] not in app.get_case_types():
            raise ValidationError(_('Case type {} not found in application {}!'.format(
                cleaned_data['case_type'],
                app.name,
            )))
        # set the app property on the form so we don't have to go back to the DB for it
        # there may be a better way to do this.
        self.app = app
        return cleaned_data


class ConfigurableFormDataSourceFromAppForm(forms.Form):

    app_id = forms.ChoiceField()
    form_id = forms.ChoiceField()

    def __init__(self, domain, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', _('Save Changes')))
        super(ConfigurableFormDataSourceFromAppForm, self).__init__(*args, **kwargs)
        apps = get_apps_in_domain(domain, full=True, include_remote=False)
        self.fields['app_id'] = forms.ChoiceField(
            label=_('Application'),
            choices=[(app._id, app.name) for app in apps]
        )
        self.fields['form_id'] = forms.ChoiceField(
            label=_('Module - Form'),
            choices=[(form.get_unique_id(), form.get_module().default_name() + ' - ' + form.default_name())
                     for form in set([form for app in apps for form in app.get_forms()])]
        )

    def clean(self):
        cleaned_data = super(ConfigurableFormDataSourceFromAppForm, self).clean()
        app = Application.get(cleaned_data['app_id'])
        form = Form.get_form(cleaned_data['form_id'])
        if form.get_app()._id != app._id:
            raise ValidationError(_('Form name {} not found in application {}').format(
                form.default_name(),
                app.name
            ))
        self.app = app
        self.form = form
        return cleaned_data
