from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _
from bootstrap3_crispy import layout as crispy
from bootstrap3_crispy.helper import FormHelper
from bootstrap3_crispy.layout import Submit
from corehq.apps.app_manager.fields import ApplicationDataSourceUIHelper
from corehq.apps.userreports.sql import get_table_name
from corehq.apps.userreports.ui.fields import ReportDataSourceField, JsonField
from dimagi.utils.decorators.memoized import memoized


class DocumentFormBase(forms.Form):
    """
    HQ specific document base form. Loosely modeled off of Django's ModelForm
    """

    def __init__(self, instance=None, read_only=False, *args, **kwargs):
        self.instance = instance
        object_data = instance._doc if instance is not None else {}
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        if not read_only:
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


VISIBILITY_CHOICES = (
    (True, _('all users')),
    (False, _('feature flag only'))
)


class ConfigurableReportEditForm(DocumentFormBase):

    config_id = forms.ChoiceField()  # gets overridden on instantiation
    title = forms.CharField()
    visible = forms.ChoiceField(label=_('Visible to:'), choices=VISIBILITY_CHOICES)
    description = forms.CharField(required=False)
    aggregation_columns = JsonField(expected_type=list)
    filters = JsonField(expected_type=list)
    columns = JsonField(expected_type=list)
    configured_charts = JsonField(expected_type=list)

    def __init__(self, domain, instance=None, read_only=False, *args, **kwargs):
        super(ConfigurableReportEditForm, self).__init__(instance, read_only, *args, **kwargs)
        self.fields['config_id'] = ReportDataSourceField(domain=domain)

    def clean_visible(self):
        return self.cleaned_data['visible'] == 'True'

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
    ('CommCareCase', _('cases')),
    ('XFormInstance', _('forms'))
)


class ConfigurableDataSourceEditForm(DocumentFormBase):

    table_id = forms.CharField()
    referenced_doc_type = forms.ChoiceField(choices=DOC_TYPE_CHOICES)
    display_name = forms.CharField()
    description = forms.CharField(required=False)
    base_item_expression = JsonField(expected_type=dict)
    configured_filter = JsonField(expected_type=dict)
    configured_indicators = JsonField(expected_type=list)
    named_filters = JsonField(required=False, expected_type=dict,
                              label=_("Named filters (optional)"))

    def __init__(self, domain, *args, **kwargs):
        self.domain = domain
        super(ConfigurableDataSourceEditForm, self).__init__(*args, **kwargs)

    def clean_table_id(self):
        table_id = self.cleaned_data['table_id']
        table_name = get_table_name(self.domain, table_id)
        if len(table_name) > 63:  # max table name length for postgres
            raise ValidationError(
                _('Table id is too long. Your table id and domain name must add up to fewer than 40 characters')
            )
        for src in self.instance.by_domain(self.domain):
            if src.table_id == table_id and src.get_id != self.instance.get_id:
                raise ValidationError(
                    _('A data source with this table id already exists. Table'
                      ' ids must be unique')
                )
        return table_id

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
            if settings.DEBUG:
                raise
            raise ValidationError(_(u'Problem with data source spec: {}').format(e))
        return cleaned_data

    def save(self, commit=False):
        self.instance.meta.build.finished = False
        self.instance.meta.build.initiated = None
        return super(ConfigurableDataSourceEditForm, self).save(commit)


class ConfigurableDataSourceFromAppForm(forms.Form):

    def __init__(self, domain, *args, **kwargs):
        super(ConfigurableDataSourceFromAppForm, self).__init__(*args, **kwargs)
        self.app_source_helper = ApplicationDataSourceUIHelper()
        self.app_source_helper.bootstrap(domain)
        report_source_fields = self.app_source_helper.get_fields()
        self.fields.update(report_source_fields)
        self.helper = FormHelper()
        self.helper.form_id = "data-source-config"
        self.helper.layout = crispy.Layout(
            crispy.Div(
                *report_source_fields.keys() + [Submit('submit', _('Save Changes'))]
            )
        )
