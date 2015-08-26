from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _
from crispy_forms import layout as crispy
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from corehq.apps.app_manager.fields import ApplicationDataSourceUIHelper
from corehq.apps.userreports.sql import get_table_name
from corehq.apps.userreports.ui import help_text
from corehq.apps.userreports.ui.fields import ReportDataSourceField, JsonField


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
    sort_expression = JsonField(expected_type=list)

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

    table_id = forms.CharField(label=_("Table ID"),
                               help_text=help_text.TABLE_ID)
    referenced_doc_type = forms.ChoiceField(
        choices=DOC_TYPE_CHOICES,
        label=_("Source Type"))
    display_name = forms.CharField(label=_("Report Title"),
                                   help_text=help_text.DISPLAY_NAME)
    description = forms.CharField(required=False,
                                  help_text=help_text.DESCRIPTION)
    base_item_expression = JsonField(expected_type=dict,
                                     help_text=help_text.BASE_ITEM_EXPRESSION)
    configured_filter = JsonField(expected_type=dict,
                                  help_text=help_text.CONFIGURED_FILTER)
    configured_indicators = JsonField(
        expected_type=list, help_text=help_text.CONFIGURED_INDICATORS)
    named_filters = JsonField(required=False, expected_type=dict,
                              label=_("Named filters (optional)"),
                              help_text=help_text.NAMED_FILTER)

    def __init__(self, domain, *args, **kwargs):
        self.domain = domain
        super(ConfigurableDataSourceEditForm, self).__init__(*args, **kwargs)

    def clean_table_id(self):
        # todo: validate table_id as [a-z][a-z0-9_]*
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
