from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

from corehq import toggles
from corehq.apps.app_manager.fields import ApplicationDataSourceUIHelper
from corehq.apps.domain.models import AllowedUCRExpressionSettings
from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.hqwebapp.widgets import BootstrapCheckboxInput
from corehq.util.metrics import metrics_counter

from ..const import DATA_SOURCE_REBUILD_RESTRICTED_AT
from ..models import guess_data_source_type
from ..util import get_table_name
from . import help_text
from .fields import JsonField, ReportDataSourceField


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

    _id = forms.CharField(required=False, disabled=True, label=_('Report ID'),
                          help_text=help_text.REPORT_ID)
    config_id = forms.ChoiceField()  # gets overridden on instantiation
    title = forms.CharField()
    visible = forms.ChoiceField(label=_('Visible to:'), choices=VISIBILITY_CHOICES)
    description = forms.CharField(required=False)
    aggregation_columns = JsonField(expected_type=list)
    filters = JsonField(expected_type=list)
    columns = JsonField(expected_type=list)
    configured_charts = JsonField(expected_type=list)
    sort_expression = JsonField(expected_type=list)
    distinct_on = JsonField(expected_type=list)

    def __init__(self, domain, instance=None, read_only=False, *args, **kwargs):
        super(ConfigurableReportEditForm, self).__init__(instance, read_only, *args, **kwargs)
        self.fields['config_id'] = ReportDataSourceField(domain=domain)

        self.helper = FormHelper()

        self.helper.form_method = 'POST'
        self.helper.form_class = 'form-horizontal'
        self.helper.form_action = '#'

        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-9'

        fields = [
            crispy.Field('config_id', css_class="hqwebapp-select2"),
            'title',
            'visible',
            'description',
            'aggregation_columns',
            'filters',
            'columns',
            'configured_charts',
            'sort_expression',
            'distinct_on',
        ]
        if instance.config_id:
            fields.append('_id')

        self.helper.layout = crispy.Layout(
            *fields
        )
        # Restrict edit for static reports
        if not read_only:
            self.helper.layout.append(
                hqcrispy.FormActions(
                    twbscrispy.StrictButton(
                        _("Save"),
                        type="submit",
                        css_class="btn btn-primary",
                    ),
                )
            )

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
        except Exception as e:
            raise ValidationError(_('Problem with report spec: {}').format(e))
        return cleaned_data

    def save(self, commit=False):
        self.instance.report_meta.edited_manually = True
        if toggles.AGGREGATE_UCRS.enabled(self.instance.domain):
            self.instance.data_source_type = guess_data_source_type(self.instance.config_id)

        return super(ConfigurableReportEditForm, self).save(commit)


DOC_TYPE_CHOICES = (
    ('CommCareCase', _('cases')),
    ('XFormInstance', _('forms'))
)


class ConfigurableDataSourceEditForm(DocumentFormBase):

    _id = forms.CharField(required=False, disabled=True, label=_('Data Source ID'),
                          help_text=help_text.DATA_SOURCE_ID)
    table_id = forms.CharField(label=_("Table ID"),
                               help_text=help_text.TABLE_ID)
    referenced_doc_type = forms.ChoiceField(
        choices=DOC_TYPE_CHOICES,
        label=_("Source Type"))
    display_name = forms.CharField(label=_("Data Source Display Name"),
                                   help_text=help_text.DISPLAY_NAME)
    description = forms.CharField(required=False,
                                  help_text=help_text.DESCRIPTION)
    base_item_expression = JsonField(expected_type=dict,
                                     help_text=help_text.BASE_ITEM_EXPRESSION)
    configured_filter = JsonField(expected_type=dict,
                                  help_text=help_text.CONFIGURED_FILTER)
    configured_indicators = JsonField(
        expected_type=list, help_text=help_text.CONFIGURED_INDICATORS)
    named_expressions = JsonField(required=False, expected_type=dict,
                              label=_("Named expressions (optional)"),
                              help_text=help_text.NAMED_EXPRESSIONS)
    named_filters = JsonField(required=False, expected_type=dict,
                              label=_("Named filters (optional)"),
                              help_text=help_text.NAMED_FILTER)
    asynchronous = forms.BooleanField(
        initial=False,
        required=False,
        label="",
        widget=BootstrapCheckboxInput(
            inline_label="Asynchronous processing"
        )
    )
    is_available_in_analytics = forms.BooleanField(
        initial=False,
        required=False,
        label="",
        widget=forms.HiddenInput(),
        help_text=help_text.COMMCARE_ANALYTICS
    )

    def __init__(self, domain, data_source_config, read_only, *args, **kwargs):
        self.domain = domain
        super(ConfigurableDataSourceEditForm, self).__init__(data_source_config, read_only, *args, **kwargs)

        if toggles.LOCATIONS_IN_UCR.enabled(domain):
            choices = self.fields['referenced_doc_type'].choices
            choices.append(
                ('Location', _('locations'))
            )
            self.fields['referenced_doc_type'].choices = choices

        if toggles.SUPERSET_ANALYTICS.enabled(domain):
            self.fields['is_available_in_analytics'].widget = BootstrapCheckboxInput(
                inline_label="Available in Analytics"
            )
        self.helper = FormHelper()

        self.helper.form_method = 'POST'
        self.helper.form_class = 'form-horizontal'
        self.helper.form_action = '#'

        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-9'

        fields = [
            'table_id',
            'referenced_doc_type',
            'display_name',
            'description',
        ]
        if 'base_item_expression' in AllowedUCRExpressionSettings.get_allowed_ucr_expressions(self.domain):
            fields.append('base_item_expression')

        fields += [
            'configured_filter',
            'configured_indicators',
            'named_expressions',
            'named_filters',
            'asynchronous',
            'is_available_in_analytics',
        ]

        if data_source_config.get_id:
            fields.append('_id')

        self.helper.layout = crispy.Layout(
            *fields,
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _("Save"),
                    type="submit",
                    css_id="gtm-save-ds-btn",
                    css_class="btn btn-primary",
                ),
            ),
        )

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
        except Exception as e:
            if settings.DEBUG:
                raise
            raise ValidationError(_('Problem with data source spec: {}').format(e))
        self._check_for_asynchronous(config)
        return cleaned_data

    def _check_for_asynchronous(self, config):
        from corehq.apps.userreports.views import number_of_records_to_be_processed

        if not config.asynchronous and toggles.RESTRICT_DATA_SOURCE_REBUILD.enabled(self.domain):
            number_of_records = number_of_records_to_be_processed(
                datasource_configuration=config
            )
            if number_of_records and number_of_records > DATA_SOURCE_REBUILD_RESTRICTED_AT:
                self.add_error(
                    'asynchronous',
                    _('This data source covers more than {record_limit} records. '
                      'Please mark it for asynchronous processing for effective building/rebuilding'
                      ).format(record_limit=f"{DATA_SOURCE_REBUILD_RESTRICTED_AT:,}")
                )

    def save(self, commit=False):
        self.instance.set_rebuild_flags()
        instance = super(ConfigurableDataSourceEditForm, self).save(commit)
        self._report_edit_datasource_metrics()
        return instance

    def _report_edit_datasource_metrics(self):
        if 'configured_filter' in self.changed_data:
            metrics_counter('commcare.ucr.datasource.change_in_filters', tags={'domain': self.domain})
        if 'configured_indicators' in self.changed_data:
            if len(self.instance.configured_indicators) > len(self.initial.get('configured_indicators', [])):
                metrics_counter('commcare.ucr.datasource.increase_in_columns', tags={'domain': self.domain})


class ConfigurableDataSourceFromAppForm(forms.Form):

    def __init__(self, domain, *args, **kwargs):
        super(ConfigurableDataSourceFromAppForm, self).__init__(*args, **kwargs)
        self.app_source_helper = ApplicationDataSourceUIHelper()
        self.app_source_helper.bootstrap(domain)
        self.fields.update(self.app_source_helper.get_fields())
        self.helper = FormHelper()
        self.helper.form_id = "data-source-config"

        self.helper.form_method = 'POST'
        self.helper.form_class = 'form-horizontal'
        self.helper.form_action = '#'

        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-9'

        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("Create Data Source from Application"),
                *self.app_source_helper.get_crispy_fields()
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _("Create Data Source"),
                    type="submit",
                    css_class="btn btn-primary",
                ),
            ),
        )
