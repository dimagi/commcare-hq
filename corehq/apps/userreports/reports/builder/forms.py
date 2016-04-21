from collections import namedtuple, OrderedDict
from itertools import chain
import json
from urllib import urlencode
import uuid
from django import forms
from django.core.urlresolvers import reverse
from django.forms import Widget
from django.forms.util import flatatt
from django.template.loader import render_to_string
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _, ugettext_noop, ugettext_lazy

from crispy_forms import layout as crispy
from crispy_forms.bootstrap import StrictButton
from crispy_forms.helper import FormHelper
from corehq.apps.style import crispy as hqcrispy

from corehq.apps.app_manager.fields import ApplicationDataSourceUIHelper
from corehq.apps.app_manager.models import (
    Application,
    Form,
)
from corehq.apps.app_manager.util import get_case_properties
from corehq.apps.app_manager.xform import XForm
from corehq.apps.style.crispy import FieldWithHelpBubble
from corehq.apps.userreports import tasks
from corehq.apps.userreports.app_manager import _clean_table_name
from corehq.apps.userreports.models import (
    DataSourceBuildInformation,
    DataSourceConfiguration,
    DataSourceMeta,
    ReportConfiguration,
    ReportMeta,
)
from corehq.apps.userreports.reports.builder import (
    DEFAULT_CASE_PROPERTY_DATATYPES,
    FORM_METADATA_PROPERTIES,
    make_case_data_source_filter,
    make_case_property_indicator,
    make_form_data_source_filter,
    make_form_meta_block_indicator,
    make_form_question_indicator,
    make_owner_name_indicator,
    get_filter_format_from_question_type,
    make_user_name_indicator)
from corehq.apps.userreports.exceptions import BadBuilderConfigError
from corehq.apps.userreports.sql import get_column_name
from corehq.apps.userreports.ui.fields import JsonField
from dimagi.utils.decorators.memoized import memoized

from corehq.toggles import UNLIMITED_REPORT_BUILDER_REPORTS


class FilterField(JsonField):
    """
    A form field with a little bit of validation for report builder report
    filter configuration.
    """
    def validate(self, value):
        super(FilterField, self).validate(value)
        for filter_conf in value:
            if filter_conf.get('format', None) not in ['', 'Choice', 'Date', 'Numeric']:
                raise forms.ValidationError("Invalid filter format!")


class Select2(Widget):
    """
    A widget for rendering an input with our knockout "select2" binding.
    Requires knockout to be included on the page.
    """

    def __init__(self, attrs=None, choices=()):
        super(Select2, self).__init__(attrs)
        self.choices = list(choices)

    def render(self, name, value, attrs=None, choices=()):
        value = '' if value is None else value
        final_attrs = self.build_attrs(attrs, name=name)

        return format_html(
            '<input{0} type="text" data-bind="select2: {1}, {2}">',
            flatatt(final_attrs),
            json.dumps(self._choices_for_binding(choices)),
            'value: {}'.format(json.dumps(value)) if value else ""
        )

    def _choices_for_binding(self, choices):
        return [{'id': id, 'text': text} for id, text in chain(self.choices, choices)]


class QuestionSelect(Widget):
    """
    A widget for rendering an input with our knockout "questionsSelect" binding.
    Requires knockout to be included on the page.
    """

    def __init__(self, attrs=None, choices=()):
        super(QuestionSelect, self).__init__(attrs)
        self.choices = list(choices)

    def render(self, name, value, attrs=None, choices=()):
        value = '' if value is None else value
        final_attrs = self.build_attrs(attrs, name=name)

        return format_html(
            """
            <input{0} data-bind='
               questionsSelect: {1},
               value: "{2}",
               optionsCaption: " "
            '/>
            """,
            flatatt(final_attrs),
            mark_safe(self.render_options(choices)),
            value
        )

    def render_options(self, choices):

        def escape(literal):
            return literal.replace('&', '&amp;').replace("'", "&#39;")

        return json.dumps(
            [{'value': escape(v), 'label': escape(l)} for v, l in chain(self.choices, choices)]
        )


class DataSourceProperty(namedtuple("DataSourceProperty", ["type", "id", "text", "column_id", "source"])):
    """
    A container class for information about data source properties

    Class attributes:

    type -- either "case_property", "form", or "meta"
    id -- A string that uniquely identifies this property. For question based
        properties this is the question id, for case based properties this is
        the case property name.
    text -- A human readable representation of the property source. For
        questions this is the question label.
    source -- For questions, this is a dict representing the question as returned
        by Xform.get_questions(), for case properties and form metadata it is just
        the name of the property.
    column_id -- A string to be used as the column_id for data source indicators
        based on this property.
    """


class DataSourceBuilder(object):
    """
    When configuring a report, one can use DataSourceBuilder to determine some
    of the properties of the required report data source, such as:
        - referenced doc type
        - filter
        - indicators
    """

    def __init__(self, domain, app, source_type, source_id):
        assert (source_type in ['case', 'form'])

        self.domain = domain
        self.app = app
        self.source_type = source_type
        # source_id is a case type of form id
        self.source_id = source_id
        if self.source_type == 'form':
            self.source_form = Form.get_form(self.source_id)
            self.source_xform = XForm(self.source_form.source)
        if self.source_type == 'case':
            prop_map = get_case_properties(
                self.app, [self.source_id], defaults=DEFAULT_CASE_PROPERTY_DATATYPES.keys()
            )
            self.case_properties = sorted(set(prop_map[self.source_id]) | {'closed'})

    @property
    @memoized
    def source_doc_type(self):
        if self.source_type == "case":
            return "CommCareCase"
        if self.source_type == "form":
            return "XFormInstance"

    @property
    @memoized
    def filter(self):
        """
        Return the filter configuration for the DataSourceConfiguration.
        """
        if self.source_type == "case":
            return make_case_data_source_filter(self.source_id)
        if self.source_type == "form":
            return make_form_data_source_filter(self.source_xform.data_node.tag_xmlns)

    def indicators(self, number_columns=None):
        """
        Return all the dict data source indicator configurations that could be
        used by a report that uses the same case type/form as this DataSourceConfiguration.
        """
        ret = []
        for prop in self.data_source_properties.values():
            if prop.type == 'meta':
                ret.append(make_form_meta_block_indicator(
                    prop.source, prop.column_id
                ))
            elif prop.type == "question":
                ret.append(make_form_question_indicator(
                    prop.source, prop.column_id
                ))
            elif prop.type == 'case_property' and prop.source == 'computed/owner_name':
                ret.append(make_owner_name_indicator(prop.column_id))
            elif prop.type == 'case_property' and prop.source == 'computed/user_name':
                ret.append(make_user_name_indicator(prop.column_id))
            elif prop.type == 'case_property':
                indicator = make_case_property_indicator(
                    prop.source, prop.column_id
                )
                if number_columns:
                    if indicator['column_id'] in number_columns:
                        indicator['datatype'] = 'decimal'
                ret.append(indicator)
        ret.append({
            "display_name": "Count",
            "type": "count",
            "column_id": "count"
        })
        return ret

    @property
    @memoized
    def data_source_properties(self):
        """
        A dictionary containing the various properties that may be used as indicators
        or columns in the data source or report.

        Keys are strings that uniquely identify properties.
        Values are DataSourceProperty instances.

        >> self.data_source_properties
        {
            "/data/question1": DataSourceProperty(
                type="question",
                id="/data/question1",
                text="Enter the child's name",
                column_id="data--question1",
                source={
                    'repeat': None,
                    'group': None,
                    'value': '/data/question1',
                    'label': 'question1',
                    'tag': 'input',
                    'type': 'Text'
                }
            ),
            "meta/deviceID": DataSourceProperty(
                type="meta",
                id="meta/deviceID",
                text="deviceID",
                column_id="meta--deviceID",
                source=("deviceID", "string")
            )
        }
        """

        if self.source_type == 'case':
            return self._get_data_source_properties_from_case(self.case_properties)

        if self.source_type == 'form':
            return self._get_data_source_properties_from_form(self.source_form, self.source_xform)

    @classmethod
    def _get_data_source_properties_from_case(cls, case_properties):
        property_map = {
            'closed': _('Case Closed'),
            'user_id': _('User ID Last Updating Case'),
            'owner_name': _('Case Owner'),
            'mobile worker': _('Mobile Worker Last Updating Case'),
        }
        properties = OrderedDict()
        for property in case_properties:
            properties[property] = DataSourceProperty(
                type='case_property',
                id=property,
                column_id=get_column_name(property),
                text=property_map.get(property, property.replace('_', ' ')),
                source=property
            )
        properties['computed/owner_name'] = cls._get_owner_name_pseudo_property()
        properties['computed/user_name'] = cls._get_user_name_pseudo_property()
        return properties

    @staticmethod
    def _get_owner_name_pseudo_property():
        # owner_name is a special pseudo-case property for which
        # the report builder will create a related_doc indicator based
        # on the owner_id of the case.
        return DataSourceProperty(
            type='case_property',
            id='computed/owner_name',
            column_id=get_column_name('computed/owner_name'),
            text=_('Case Owner'),
            source='computed/owner_name'
        )

    @staticmethod
    def _get_user_name_pseudo_property():
        # user_name is a special pseudo case property for which
        # the report builder will create a related_doc indicator based on the
        # user_id of the case
        return DataSourceProperty(
            type='case_property',
            id='computed/user_name',
            column_id=get_column_name('computed/user_name'),
            text=_('Mobile Worker Last Updating Case'),
            source='computed/user_name',
        )

    @staticmethod
    def _get_data_source_properties_from_form(form, form_xml):
        property_map = {
            'username': _('User Name'),
            'userID': _('User ID'),
            'timeStart': _('Date Form Started'),
            'timeEnd': _('Date Form Completed'),
        }
        properties = OrderedDict()
        questions = form_xml.get_questions([])
        for prop in FORM_METADATA_PROPERTIES:
            properties[prop[0]] = DataSourceProperty(
                type="meta",
                id=prop[0],
                column_id=get_column_name(prop[0].strip("/")),
                text=property_map.get(prop[0], prop[0]),
                source=prop,
            )
        for question in questions:
            properties[question['value']] = DataSourceProperty(
                type="question",
                id=question['value'],
                column_id=get_column_name(question['value'].strip("/")),
                text=question['label'],
                source=question,
            )
        if form.get_app().auto_gps_capture:
            properties['location'] = DataSourceProperty(
                type="meta",
                id='location',
                column_id=get_column_name('location'),
                text='location',
                source=(['location', '#text'], 'Text'),
            )
        return properties

    @property
    @memoized
    def data_source_name(self):
        if self.source_type == 'form':
            return u"{} (v{})".format(self.source_form.default_name(), self.app.version)
        if self.source_type == 'case':
            return u"{} (v{})".format(self.source_id, self.app.version)

    def get_existing_match(self):
        return DataSourceConfiguration.view(
            'userreports/data_sources_by_build_info',
            key=[
                self.domain,
                self.source_doc_type,
                self.source_id,
                self.app._id,
                self.app.version
            ],
            include_docs=True,
            reduce=False
        ).one()


def _legend(title, subtext):
    """
    Return a string to be used in a crispy form Fieldset legend.
    This function is just a light wrapped around some simple templating.
    """
    return '{title}</br><div class="subtext"><small>{subtext}</small></div>'.format(
        title=title, subtext=subtext
    )


class DataSourceForm(forms.Form):
    report_name = forms.CharField()
    chart_type = forms.ChoiceField(
        choices=[
            ('bar', _('Bar')),
            ('pie', _("Pie")),
        ],
    )

    def __init__(self, domain, report_type, *args, **kwargs):
        super(DataSourceForm, self).__init__(*args, **kwargs)
        self.domain = domain
        self.report_type = report_type

        self.app_source_helper = ApplicationDataSourceUIHelper()
        self.app_source_helper.source_type_field.label = _('Forms or Cases')
        self.app_source_helper.source_type_field.choices = [("case", _("Cases")), ("form", _("Forms"))]
        self.app_source_helper.source_field.label = '<span data-bind="text: labelMap[sourceType()]"></span>'
        self.app_source_helper.bootstrap(self.domain)
        report_source_fields = self.app_source_helper.get_fields()
        report_source_help_texts = {
            "source_type": _("<strong>Form</strong>: display data from form submissions.<br/><strong>Case</strong>: display data from your cases. You must be using case management for this option."),
            "application": _("Which application should the data come from?"),
            "source": _("Choose the case type or form from which to retrieve data for this report."),
        }
        self.fields.update(report_source_fields)

        self.fields['chart_type'].required = self.report_type == "chart"

        self.helper = FormHelper()
        self.helper.form_class = "form form-horizontal"
        self.helper.form_id = "report-builder-form"
        self.helper.label_class = 'col-sm-3 col-md-2 col-lg-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'

        chart_type_crispy_field = None
        if self.report_type == 'chart':
            chart_type_crispy_field = FieldWithHelpBubble('chart_type', help_bubble_text=_("<strong>Bar</strong> shows one vertical bar for each value in your case or form. <strong>Pie</strong> shows what percentage of the total each value is."))
        report_source_crispy_fields = []
        for k in report_source_fields.keys():
            if k in report_source_help_texts:
                report_source_crispy_fields.append(FieldWithHelpBubble(
                    k, help_bubble_text=report_source_help_texts[k]
                ))
            else:
                report_source_crispy_fields.append(k)

        top_fields = [
            FieldWithHelpBubble(
                'report_name',
                help_bubble_text=_('Web users will see this name in the "Reports" section of CommCareHQ and can click to view the report'))
        ]
        if chart_type_crispy_field:
            top_fields.append(chart_type_crispy_field)

        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _('{} Report'.format(self.report_type.capitalize())),
                *top_fields
            ),
            crispy.Fieldset(
                _('Data'), *report_source_crispy_fields
            ),
            hqcrispy.FormActions(
                StrictButton(
                    _('Next'),
                    type="submit",
                    css_class="btn-primary",
                )
            ),
        )

    @property
    def sources_map(self):
        return self.app_source_helper.all_sources

    def get_selected_source(self):
        return self.app_source_helper.get_app_source(self.cleaned_data)

    def clean(self):
        """
        Raise a validation error if there are already 5 data sources and this
        report won't be able to use one of the existing ones.
        """
        cleaned_data = super(DataSourceForm, self).clean()

        existing_reports = ReportConfiguration.by_domain(self.domain)
        builder_reports = filter(lambda report: report.report_meta.created_by_builder, existing_reports)
        if len(builder_reports) >= 5 and not UNLIMITED_REPORT_BUILDER_REPORTS.enabled(self.domain):
            raise forms.ValidationError(_(
                "Too many reports!\n"
                "Creating this report would cause you to go over the maximum "
                "number of report builder reports allowed in this domain. The current "
                "limit is 5. "
                "To continue, delete another report and try again. "
            ))

        return cleaned_data

_shared_properties = ['exists_in_current_version', 'display_text', 'property', 'data_source_field']
FilterViewModel = namedtuple("FilterViewModel", _shared_properties + ['format'])
ColumnViewModel = namedtuple("ColumnViewModel", _shared_properties + ['calculation'])


class ConfigureNewReportBase(forms.Form):
    filters = FilterField(required=False)
    button_text = ugettext_noop('Done')

    def __init__(self, report_name, app_id, source_type, report_source_id, existing_report=None, *args, **kwargs):
        """
        This form can be used to create a new ReportConfiguration, or to modify
        an existing one if existing_report is set.
        """
        super(ConfigureNewReportBase, self).__init__(*args, **kwargs)
        self.existing_report = existing_report

        if self.existing_report:
            self._bootstrap(self.existing_report)
            self.button_text = _('Update Report')
        else:
            self.report_name = report_name
            assert source_type in ['case', 'form']
            self.source_type = source_type
            self.report_source_id = report_source_id
            self.app = Application.get(app_id)

        self.domain = self.app.domain
        self.ds_builder = DataSourceBuilder(
            self.domain, self.app, self.source_type, self.report_source_id
        )
        self.data_source_properties = self.ds_builder.data_source_properties
        self._properties_by_column = {
            p.column_id: p for p in self.data_source_properties.values()
        }

        # NOTE: The corresponding knockout view model is defined in:
        #       templates/userreports/partials/report_builder_configure_report.html
        self.helper = FormHelper()
        self.helper.form_class = "form form-horizontal"
        self.helper.label_class = 'col-sm-3 col-md-2 col-lg-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.attrs['data_bind'] = "submit: submitHandler"
        self.helper.form_id = "report-config-form"

        buttons = [
            StrictButton(
                _(self.button_text),
                css_class="btn btn-primary disable-on-submit",
                type="submit",
            )
        ]
        # Add a back button if we aren't editing an existing report
        if not self.existing_report:
            buttons.insert(
                0,
                crispy.HTML(
                    '<a class="btn btn-default" href="{}" style="margin-right: 4px">{}</a>'.format(
                        reverse(
                            'report_builder_select_source',
                            args=(self.domain, self.report_type),
                        ),
                        _('Back')
                    )
                ),
            )
        # Add a "delete report" button if we are editing an existing report
        else:
            buttons.insert(
                0,
                crispy.HTML(
                    '<a id="delete-report-button" class="btn btn-danger pull-right" href="{}">{}</a>'.format(
                        reverse(
                            'delete_configurable_report',
                            args=(self.domain, self.existing_report._id),
                        ) + "?{}".format(urlencode(
                            {'redirect': reverse('reports_home', args=[self.domain])}
                        )),
                        _('Delete Report')
                    )
                )
            )
        self.helper.layout = crispy.Layout(
            self.container_fieldset,
            hqcrispy.FormActions(crispy.ButtonHolder(*buttons)),
        )

    def _bootstrap(self, existing_report):
        """
        Use an existing report to initialize some of the instance variables of this
        form. This method is used when editing an existing report.
        """
        self.report_name = existing_report.title
        self.source_type = {
            "CommCareCase": "case",
            "XFormInstance": "form"
        }[existing_report.config.referenced_doc_type]
        self.report_source_id = existing_report.config.meta.build.source_id
        app_id = existing_report.config.meta.build.app_id
        if app_id:
            self.app = Application.get(app_id)
        else:
            raise BadBuilderConfigError(_(
                "Report builder data source doesn't reference an application. "
                "It is likely this report has been customized and it is no longer editable. "
            ))

    @property
    def column_config_template(self):
        return render_to_string('userreports/partials/property_list_configuration.html')

    @property
    def container_fieldset(self):
        """
        Return the first fieldset in the form.
        """
        return crispy.Fieldset(
            "",
            self.filter_fieldset
        )

    @property
    def filter_fieldset(self):
        """
        Return a fieldset representing the markup used for configuring the
        report filters.
        """
        return crispy.Fieldset(
            _legend(
                _("Filters"),
                _("Add filters to your report to allow viewers to select which data the report will display. These filters will be displayed at the top of your report.")
            ),
            crispy.Div(
                crispy.HTML(self.column_config_template), id="filters-table", data_bind='with: filtersList'
            ),
            crispy.Hidden('filters', None, data_bind="value: filtersList.serializedProperties")
        )

    def _build_data_source(self):
        data_source_config = DataSourceConfiguration(
            domain=self.domain,
            display_name=self.ds_builder.data_source_name,
            referenced_doc_type=self.ds_builder.source_doc_type,
            # The uuid gets truncated, so it's not really universally unique.
            table_id=_clean_table_name(self.domain, str(uuid.uuid4().hex)),
            configured_filter=self.ds_builder.filter,
            configured_indicators=self.ds_builder.indicators(self._number_columns),
            meta=DataSourceMeta(build=DataSourceBuildInformation(
                source_id=self.report_source_id,
                app_id=self.app._id,
                app_version=self.app.version,
            ))
        )
        data_source_config.validate()
        data_source_config.save()
        tasks.rebuild_indicators.delay(data_source_config._id)
        return data_source_config._id

    def update_report(self):
        matching_data_source = self.ds_builder.get_existing_match()
        if matching_data_source:
            reactivated = False
            if matching_data_source._id != self.existing_report.config_id:

                # If no one else is using the current data source, delete it.
                data_source = DataSourceConfiguration.get(self.existing_report.config_id)
                if data_source.get_report_count() <= 1:
                    data_source.deactivate()

                self.existing_report.config_id = matching_data_source._id
            elif matching_data_source.is_deactivated:
                matching_data_source.is_deactivated = False
                reactivated = True
            changed = False
            indicators = self.ds_builder.indicators(self._number_columns)
            if matching_data_source.configured_indicators != indicators:
                matching_data_source.configured_indicators = indicators
                changed = True
            if changed or reactivated:
                matching_data_source.save()
                tasks.rebuild_indicators.delay(matching_data_source._id)
        else:
            # Delete the old one if no other reports use it
            old_data_source = DataSourceConfiguration.get(self.existing_report.config_id)
            if old_data_source.get_report_count() <= 1:
                old_data_source.deactivate()

            data_source_config_id = self._build_data_source()
            self.existing_report.config_id = data_source_config_id

        self.existing_report.aggregation_columns = self._report_aggregation_cols
        self.existing_report.columns = self._report_columns
        self.existing_report.filters = self._report_filters
        self.existing_report.configured_charts = self._report_charts
        self.existing_report.validate()
        self.existing_report.save()
        return self.existing_report

    def create_report(self):
        """
        Creates data source and report config.
        """
        matching_data_source = self.ds_builder.get_existing_match()
        if matching_data_source:
            data_source_config_id = matching_data_source._id
            reactivated = False
            if matching_data_source.is_deactivated:
                matching_data_source.is_deactivated = False
                reactivated = True
            changed = False
            indicators = self.ds_builder.indicators(self._number_columns)
            if matching_data_source.configured_indicators != indicators:
                matching_data_source.configured_indicators = indicators
                changed = True
            if changed or reactivated:
                matching_data_source.save()
                tasks.rebuild_indicators.delay(matching_data_source._id)
        else:
            data_source_config_id = self._build_data_source()

        report = ReportConfiguration(
            domain=self.domain,
            config_id=data_source_config_id,
            title=self.report_name,
            aggregation_columns=self._report_aggregation_cols,
            columns=self._report_columns,
            filters=self._report_filters,
            configured_charts=self._report_charts,
            report_meta=ReportMeta(
                created_by_builder=True,
                builder_report_type=self.report_type
            )
        )
        report.validate()
        report.save()
        return report

    @property
    @memoized
    def initial_filters(self):
        if self.existing_report:
            return [self._get_view_model(f) for f in self.existing_report.filters]
        if self.source_type == 'case':
            return self._default_case_report_filters
        else:
            # self.source_type == 'form'
            return self._default_form_report_filters

    @property
    @memoized
    def _default_case_report_filters(self):
        return [
            FilterViewModel(
                exists_in_current_version=True,
                property='closed',
                data_source_field=None,
                display_text=_('Closed'),
                format='Choice',
            ),
            FilterViewModel(
                exists_in_current_version=True,
                property='computed/owner_name',
                data_source_field=None,
                display_text=_('Case Owner'),
                format='Choice',
            ),
        ]

    @property
    @memoized
    def _default_form_report_filters(self):
        return [
            FilterViewModel(
                exists_in_current_version=True,
                property='timeEnd',
                data_source_field=None,
                display_text='Form completion time',
                format='Date',
            ),
        ]

    def _get_view_model(self, filter):
        """
        Given a ReportFilter, return a FilterViewModel representing
        the knockout view model representing this filter in the report builder.

        """
        filter_type_map = {
            'dynamic_choice_list': 'Choice',
            # This exists to handle the `closed` filter that might exist
            'choice_list': 'Choice',
            'date': 'Date',
            'numeric': 'Numeric'
        }
        exists = self._column_exists(filter['field'])
        return FilterViewModel(
            exists_in_current_version=exists,
            display_text=filter['display'],
            format=filter_type_map[filter['type']],
            property=self._get_property_from_column(filter['field']) if exists else None,
            data_source_field=filter['field'] if not exists else None
        )

    def _get_property_from_column(self, col):
        column = self._properties_by_column.get(col)
        if column:
            return column.id

    def _column_exists(self, column_id):
        """
        Return True if this column corresponds to a question/case property in
        the current version of this form/case configuration.

        This could be true if a user makes a report, modifies the app, then
        edits the report.

        column_id is a string like "data_date_q_d1b3693e"
        """
        return column_id in self._properties_by_column

    @property
    def _report_aggregation_cols(self):
        return ['doc_id']

    @property
    def _report_columns(self):
        return []

    @property
    @memoized
    def _number_columns(self):
        return [col["field"] for col in self._report_columns if col.get("aggregation", None) in ["avg", "sum"]]

    @property
    def _report_filters(self):
        """
        Return the dict filter configurations to be used by the
        ReportConfiguration that this form produces.
        """
        filter_type_map = {
            'Choice': 'dynamic_choice_list',
            'Date': 'date',
            'Numeric': 'numeric'
        }

        def _make_report_filter(conf, index):
            property = self.data_source_properties[conf["property"]]
            col_id = property.column_id

            selected_filter_type = conf['format']
            if not selected_filter_type or self.source_type == 'form':
                if property.type == 'question':
                    filter_format = get_filter_format_from_question_type(
                        property.source['type']
                    )
                else:
                    assert property.type == 'meta'
                    filter_format = get_filter_format_from_question_type(
                        property.source[1]
                    )
            else:
                filter_format = filter_type_map[selected_filter_type]

            ret = {
                "field": col_id,
                "slug": "{}_{}".format(col_id, index),
                "display": conf["display_text"],
                "type": filter_format
            }
            if conf['format'] == 'Date':
                ret.update({'compare_as_string': True})
            return ret

        filter_configs = self.cleaned_data['filters']
        filters = [_make_report_filter(f, i) for i, f in enumerate(filter_configs)]
        if self.source_type == 'case':
            # The UI doesn't support specifying "choice_list" filters, only "dynamic_choice_list" filters.
            # But, we want to make the open/closed filter a cleaner "choice_list" filter, so we do that here.
            self._convert_closed_filter_to_choice_list(filters)
        return filters

    @classmethod
    def _convert_closed_filter_to_choice_list(cls, filters):
        for f in filters:
            if f['field'] == get_column_name('closed') and f['type'] == 'dynamic_choice_list':
                f['type'] = 'choice_list'
                f['choices'] = [
                    {'value': 'True'},
                    {'value': 'False'}
                ]

    @property
    def _report_charts(self):
        return []


class ConfigureBarChartReportForm(ConfigureNewReportBase):
    group_by = forms.ChoiceField(label=_("Bar Chart Categories"))
    report_type = 'chart'

    def __init__(self, report_name, app_id, source_type, report_source_id, existing_report=None, *args, **kwargs):
        super(ConfigureBarChartReportForm, self).__init__(
            report_name, app_id, source_type, report_source_id, existing_report, *args, **kwargs
        )
        if self.source_type == "form":
            self.fields['group_by'].widget = QuestionSelect(attrs={'class': 'input-large'})
        else:
            self.fields['group_by'].widget = Select2(attrs={'class': 'input-large'})
        self.fields['group_by'].choices = self._group_by_choices

        # Set initial value of group_by
        if self.existing_report:
            existing_agg_cols = existing_report.aggregation_columns
            assert len(existing_agg_cols) < 2
            if existing_agg_cols:
                self.fields['group_by'].initial = self._get_property_from_column(existing_agg_cols[0])

    @property
    def container_fieldset(self):
        return crispy.Fieldset(
            _('Chart'),
            FieldWithHelpBubble(
                'group_by',
                help_bubble_text=_(
                    "The values of the selected property will be aggregated "
                    "and shown as bars in the chart."
                ),
                placeholder=_("Select Property..."),
            ),
            self.filter_fieldset
        )

    @property
    def aggregation_field(self):
        return self.cleaned_data["group_by"]

    @property
    def _report_aggregation_cols(self):
        return [
            self.data_source_properties[self.aggregation_field].column_id
        ]

    @property
    def _report_charts(self):
        agg_col = self.data_source_properties[self.aggregation_field].column_id
        return [{
            "type": "multibar",
            "x_axis_column": agg_col,
            "y_axis_columns": ["count"],
        }]

    @property
    def _report_columns(self):
        agg_col_id = self.data_source_properties[self.aggregation_field].column_id
        agg_disp = self.data_source_properties[self.aggregation_field].text
        return [
            {
                "format": "default",
                "aggregation": "simple",
                "field": agg_col_id,
                "type": "field",
                "display": agg_disp
            },
            {
                "format": "default",
                "aggregation": "sum",
                "field": "count",
                "type": "field",
                "display": "Count"
            }
        ]

    @property
    def _group_by_choices(self):
        return [(p.id, p.text) for p in self.data_source_properties.values()]


class ConfigurePieChartReportForm(ConfigureBarChartReportForm):
    group_by = forms.ChoiceField(label=_("Pie Chart Segments"))

    @property
    def container_fieldset(self):
        return crispy.Fieldset(
            _('Chart Properties'),
            FieldWithHelpBubble(
                'group_by',
                help_bubble_text=_(
                    "The values of the selected property will be aggregated "
                    "and shows as the sections of the pie chart."
                ),
                placeholder=_(
                    "Select Property..."
                ),
            ),
            self.filter_fieldset
        )

    @property
    def _report_charts(self):
        agg = self.data_source_properties[self.aggregation_field].column_id
        return [{
            "type": "pie",
            "aggregation_column": agg,
            "value_column": "count",
        }]


class ConfigureListReportForm(ConfigureNewReportBase):
    report_type = 'list'
    columns = JsonField(
        expected_type=list,
        null_values=([],),
        required=True,
        widget=forms.HiddenInput,
        error_messages={"required": ugettext_lazy("At least one column is required")},
    )
    column_legend_fine_print = ugettext_noop("Add columns to your report to display information from cases or form submissions. You may rearrange the order of the columns by dragging the arrows next to the column.")

    @property
    def container_fieldset(self):
        source_name = ''
        if self.source_type == 'case':
            source_name = self.report_source_id
        if self.source_type == 'form':
            source_name = Form.get_form(self.report_source_id).default_name()
        return crispy.Fieldset(
            '',
            crispy.Fieldset(
                _legend(
                    _("Rows"),
                    _('This report will show one row for each {name} {source}').format(
                        name=source_name, source=self.source_type
                    )
                )
            ),
            self.column_fieldset,
            self.filter_fieldset
        )

    @property
    def column_fieldset(self):
        return crispy.Fieldset(
            _legend(_("Columns"), _(self.column_legend_fine_print)),
            crispy.Div(
                crispy.HTML(self.column_config_template), id="columns-table", data_bind='with: columnsList'
            ),
            hqcrispy.HiddenFieldWithErrors('columns', None, data_bind="value: columnsList.serializedProperties"),
        )

    @property
    @memoized
    def initial_columns(self):
        if self.existing_report:
            reverse_agg_map = {
                'avg': 'Average',
                'sum': 'Sum',
                'simple': 'Count per Choice'
            }
            cols = []
            for c in self.existing_report.columns:
                exists = self._column_exists(c['field'])
                cols.append(
                    ColumnViewModel(
                        display_text=c['display'],
                        exists_in_current_version=exists,
                        property=self._get_property_from_column(c['field']) if exists else None,
                        data_source_field=c['field'] if not exists else None,
                        calculation=reverse_agg_map.get(c.get('aggregation'), _('Count per Choice'))
                    )
                )
            return cols
        return [ColumnViewModel(
                    display_text='',
                    exists_in_current_version=True,
                    property=None,
                    data_source_field=None,
                    calculation=_('Count per Choice')
                )]

    @property
    def _report_columns(self):
        def _make_column(conf, index):
            return {
                "format": "default",
                "aggregation": "simple",
                "field": self.data_source_properties[conf['property']].column_id,
                "column_id": "column_{}".format(index),
                "type": "field",
                "display": conf['display_text']
            }
        return [_make_column(conf, i) for i, conf in enumerate(self.cleaned_data['columns'])]

    @property
    def _report_aggregation_cols(self):
        return ['doc_id']


class ConfigureTableReportForm(ConfigureListReportForm, ConfigureBarChartReportForm):
    report_type = 'table'
    column_legend_fine_print = ugettext_noop('Add columns for this report to aggregate. Each property you add will create a column for every value of that property.  For example, if you add a column for a yes or no question, the report will show a column for "yes" and a column for "no."')
    group_by = forms.ChoiceField(label=_("Show one row for each"))

    @property
    def container_fieldset(self):
        return crispy.Fieldset(
            "",
            self.column_fieldset,
            crispy.Fieldset(
                _legend(
                    _("Rows"),
                    _('Choose which property this report will group its results by. Each value of this property will be a row in the table. For example, if you choose a yes or no question, the report will show a row for "yes" and a row for "no."'),
                ),
                'group_by',
            ),
            self.filter_fieldset
        )

    @property
    def _report_charts(self):
        # Override the behavior inherited from ConfigureBarChartReportForm
        return []

    @property
    def _report_columns(self):
        agg_field_id = self.data_source_properties[self.aggregation_field].column_id
        agg_field_text = self.data_source_properties[self.aggregation_field].text

        def _make_column(conf, index):
            aggregation_map = {'Count per Choice': 'simple',
                                'Sum': 'sum',
                                'Average': 'avg'}
            return {
                "format": "default",
                "aggregation": aggregation_map[conf['calculation']],
                "field": self.data_source_properties[conf['property']].column_id,
                "column_id": "column_{}".format(index),
                "type": "field",
                "display": conf['display_text'],
                "transform": {'type': 'custom', 'custom_type': 'short_decimal_display'}
            }

        columns = [_make_column(conf, i) for i, conf in enumerate(self.cleaned_data['columns'])]

        # Add the aggregation indicator to the columns if it's not already present.
        displaying_agg_column = bool([c for c in columns if c['field'] == agg_field_id])
        if not displaying_agg_column:
            columns = [{
                'format': 'default',
                'aggregation': 'simple',
                "type": "field",
                'field': agg_field_id,
                'display': agg_field_text
            }] + columns

        # Expand all columns except for the column being used for aggregation.
        for c in columns:
            if c['field'] != agg_field_id and c['aggregation'] == 'simple':
                c['aggregation'] = "expand"
        return columns

    @property
    @memoized
    def initial_columns(self):
        columns = super(ConfigureTableReportForm, self).initial_columns

        # Remove the aggregation indicator from the columns.
        # It gets removed because we want it to be a column in the report,
        # but we don't want it to appear in the builder.
        if self.existing_report:
            agg_properties = [
                self._get_property_from_column(c)
                for c in self.existing_report.aggregation_columns
            ]
            return [c for c in columns if c.property not in agg_properties]
        return columns

    @property
    @memoized
    def _report_aggregation_cols(self):
        # we want the bar chart behavior, which is reproduced here:
        return [
            self.data_source_properties[self.aggregation_field].column_id
        ]


class ConfigureWorkerReportForm(ConfigureTableReportForm):
    # This is a ConfigureTableReportForm, but with a predetermined aggregation
    report_type = 'worker'
    column_legend_fine_print = ugettext_noop('Add columns for this report to aggregate. Each property you add will create a column for every value of that property. For example, if you add a column for a yes or no question, the report will show a column for "yes" and a column for "no".')

    def __init__(self, *args, **kwargs):
        super(ConfigureWorkerReportForm, self).__init__(*args, **kwargs)
        self.fields.pop('group_by')

    @property
    def aggregation_field(self):
        if self.source_type == "form":
            return "username"
        if self.source_type == "case":
            return "computed/user_name"

    @property
    @memoized
    def _default_case_report_filters(self):
        return [
            FilterViewModel(
                exists_in_current_version=True,
                property='closed',
                data_source_field=None,
                display_text='closed',
                format='Choice',
            ),
            FilterViewModel(
                exists_in_current_version=True,
                property='computed/user_name',
                data_source_field=None,
                display_text='user name',
                format='Choice',
            ),
        ]

    @property
    def container_fieldset(self):
        return crispy.Fieldset(
            '',
            crispy.Fieldset(
                _legend(
                    _("Rows"),
                    _('This report will show one row for each mobile worker'),
                )
            ),
            self.column_fieldset,
            self.filter_fieldset
        )


class ConfigureMapReportForm(ConfigureListReportForm):
    report_type = 'map'
    location = forms.ChoiceField(label="Location field")

    def __init__(self, report_name, app_id, source_type, report_source_id, existing_report=None, *args, **kwargs):
        super(ConfigureMapReportForm, self).__init__(
            report_name, app_id, source_type, report_source_id, existing_report, *args, **kwargs
        )
        if self.source_type == "form":
            self.fields['location'].widget = QuestionSelect(attrs={'class': 'input-large'})
        else:
            self.fields['location'].widget = Select2(attrs={'class': 'input-large'})
        self.fields['location'].choices = self._location_choices

        # Set initial value of location
        if self.existing_report and existing_report.location_column_id:
            existing_loc_col = existing_report.location_column_id
            self.fields['location'].initial = self._get_property_from_column(existing_loc_col)

    @property
    def _location_choices(self):
        return [(p.id, p.text) for p in self.data_source_properties.values()]

    @property
    def container_fieldset(self):
        return crispy.Fieldset(
            "",
            self.column_fieldset,
            crispy.Fieldset(
                _legend(
                    _("Location"),
                    _('Choose which property represents the location.'),
                ),
                'location',
            ),
            self.filter_fieldset
        )

    @property
    @memoized
    def initial_columns(self):
        columns = super(ConfigureMapReportForm, self).initial_columns

        # Remove the location indicator from the columns.
        # It gets removed because we want it to be a column in the report,
        # but we don't want it to appear in the builder.
        if self.existing_report and self.existing_report.location_column_id:
            col_id = self.existing_report.location_column_id
            location_property = self._get_property_from_column(col_id)
            return [c for c in columns if c.property != location_property]
        return columns

    @property
    def location_field(self):
        return self.cleaned_data["location"]

    @property
    def _report_columns(self):
        loc_field_id = self.data_source_properties[self.location_field].column_id
        loc_field_text = self.data_source_properties[self.location_field].text

        columns = super(ConfigureMapReportForm, self)._report_columns

        # Add the location indicator to the columns if it's not already present.
        displaying_loc_column = bool([c for c in columns if c['field'] == loc_field_id])
        if not displaying_loc_column:
            columns = columns + [{
                "column_id": loc_field_id,
                "type": "location",
                'field': loc_field_id,
                'display': loc_field_text
            }]

        return columns
