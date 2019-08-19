from __future__ import absolute_import
from __future__ import unicode_literals
from collections import defaultdict
from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager import models
from corehq.apps.app_manager.const import MOBILE_UCR_MIGRATING_TO_2, MOBILE_UCR_VERSION_2
from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
from corehq.apps.app_manager.models import ReportModule, MobileSelectFilter
from corehq.apps.app_manager.suite_xml.xml_models import Locale, Text, Command, Entry, \
    SessionDatum, Detail, Header, Field, Template, GraphTemplate, Xpath, XpathVariable
from corehq.apps.reports_core.filters import DynamicChoiceListFilter, ChoiceListFilter
from corehq.apps.userreports.exceptions import ReportConfigurationNotFoundError
from corehq.util.python_compatibility import soft_assert_type_text
from corehq.util.quickcache import quickcache
import six


COLUMN_XPATH_TEMPLATE = "column[@id='{}']"
COLUMN_XPATH_TEMPLATE_V2 = "{}"
COLUMN_XPATH_CLIENT_TEMPLATE = "column[@id='<%= id %>']"
COLUMN_XPATH_CLIENT_TEMPLATE_V2 = "<%= id %>"


def _get_column_xpath_template(new_mobile_ucr_restore):
    return COLUMN_XPATH_TEMPLATE_V2 if new_mobile_ucr_restore else COLUMN_XPATH_TEMPLATE


def get_column_xpath_client_template(new_mobile_ucr_restore):
    return COLUMN_XPATH_CLIENT_TEMPLATE_V2 if new_mobile_ucr_restore else COLUMN_XPATH_CLIENT_TEMPLATE


@quickcache(['report_module.unique_id'])
def _load_reports(report_module):
    if not report_module._loaded:
        # load reports in bulk to avoid hitting the database for each one
        try:
            all_report_configs = report_module.reports
            # generate id mapping to not rely on reports to be returned in the same order
            id_mappings = {report_config._id: report_config for report_config in all_report_configs}
            for report_config in report_module.report_configs:
                report_config._report = id_mappings[report_config.report_id]
            report_module._loaded = True
        except ReportConfigurationNotFoundError:
            pass


class ReportModuleSuiteHelper(object):

    def __init__(self, report_module):
        assert isinstance(report_module, ReportModule)
        self.report_module = report_module
        self.domain = self.app.domain
        self._loaded = None

    @property
    def app(self):
        return self.report_module.get_app()

    @property
    def mobile_ucr_restore_version(self):
        return self.app.mobile_ucr_restore_version

    @property
    def new_mobile_ucr_restore(self):
        return self.mobile_ucr_restore_version in (MOBILE_UCR_MIGRATING_TO_2, MOBILE_UCR_VERSION_2)

    def get_details(self):
        _load_reports(self.report_module)
        for config in self.report_module.report_configs:
            for filter_slug, f in MobileSelectFilterHelpers.get_filters(config, self.domain):
                yield (MobileSelectFilterHelpers.get_select_detail_id(config, filter_slug),
                       MobileSelectFilterHelpers.get_select_details(config, filter_slug, self.domain), True)
            yield (_get_select_detail_id(config), _get_select_details(config), True)
            yield (_get_summary_detail_id(config),
                   _get_summary_details(config, self.domain, self.report_module, self.new_mobile_ucr_restore), True)

    def get_custom_entries(self):
        _load_reports(self.report_module)
        for config in self.report_module.report_configs:
            yield _get_config_entry(config, self.domain, self.new_mobile_ucr_restore)


def _get_config_entry(config, domain, new_mobile_ucr_restore=False):
    if new_mobile_ucr_restore:
        datum_string = "instance('commcare-reports:{}')/rows"
    else:
        datum_string = "instance('reports')/reports/report[@id='{}']"

    return Entry(
        command=Command(
            id='reports.{}'.format(config.uuid),
            text=Text(
                locale=Locale(id=id_strings.report_name(config.uuid)),
            ),
        ),
        datums=[
            SessionDatum(
                detail_select=MobileSelectFilterHelpers.get_select_detail_id(config, filter_slug),
                id=MobileSelectFilterHelpers.get_datum_id(config, filter_slug),
                nodeset=MobileSelectFilterHelpers.get_options_nodeset(config, filter_slug, new_mobile_ucr_restore),
                value='./@value',
            )
            for filter_slug, f in MobileSelectFilterHelpers.get_filters(config, domain)
        ] + [
            SessionDatum(
                detail_confirm=_get_summary_detail_id(config),
                detail_select=_get_select_detail_id(config),
                id='report_id_{}'.format(config.uuid),
                nodeset=datum_string.format(config.instance_id),
                value='./@id',
                autoselect="true"
            ),
        ]
    )


def _get_select_detail_id(config):
    return 'reports.{}.select'.format(config.uuid)


def _get_summary_detail_id(config):
    return 'reports.{}.summary'.format(config.uuid)


def _get_select_details(config):
    return models.Detail(custom_xml=Detail(
        id=_get_select_detail_id(config),
        title=Text(
            locale=Locale(id=id_strings.report_menu()),
        ),
        fields=[
            Field(
                header=Header(
                    text=Text(
                        locale=Locale(id=id_strings.report_name_header()),
                    )
                ),
                template=Template(
                    text=Text(
                        locale=Locale(id=id_strings.report_name(config.uuid))
                    )
                ),
            )
        ]
    ).serialize().decode('utf-8'))


def get_data_path(config, domain, new_mobile_ucr_restore=False):
    if new_mobile_ucr_restore:
        data_path_string = "instance('commcare-reports:{}')/rows/row[@is_total_row='False']{}"
    else:
        data_path_string = "instance('reports')/reports/report[@id='{}']/rows/row[@is_total_row='False']{}"

    return data_path_string.format(
        config.instance_id,
        MobileSelectFilterHelpers.get_data_filter_xpath(config, domain, new_mobile_ucr_restore)
    )


def _get_summary_details(config, domain, module, new_mobile_ucr_restore=False):
    def _get_graph_fields():
        from corehq.apps.userreports.reports.specs import MultibarChartSpec
        from corehq.apps.app_manager.models import GraphConfiguration, GraphSeries

        def _locale_config(key):
            return id_strings.mobile_ucr_configuration(
                module,
                config.uuid,
                key
            )

        def _locale_series_config(index, key):
            return id_strings.mobile_ucr_series_configuration(
                module,
                config.uuid,
                index,
                key
            )

        def _locale_annotation(index):
            return id_strings.mobile_ucr_annotation(
                module,
                config.uuid,
                index
            )


        for chart_config in config.report(domain).charts:
            if isinstance(chart_config, MultibarChartSpec):
                graph_config = config.complete_graph_configs.get(chart_config.chart_id, GraphConfiguration(
                    series=[GraphSeries() for c in chart_config.y_axis_columns],
                ))

                # Reconcile graph_config.series with any additions/deletions in chart_config.y_axis_columns
                while len(chart_config.y_axis_columns) > len(graph_config.series):
                    graph_config.series.append(GraphSeries())
                if len(chart_config.y_axis_columns) < len(graph_config.series):
                    graph_config.series = graph_config.series[:len(chart_config.y_axis_columns)]

                for index, column in enumerate(chart_config.y_axis_columns):
                    graph_config.series[index].data_path = (
                        graph_config.series[index].data_path or
                        get_data_path(config, domain, new_mobile_ucr_restore)
                    )
                    graph_config.series[index].x_function = (
                        graph_config.series[index].x_function
                        or _get_column_xpath_template(new_mobile_ucr_restore).format(chart_config.x_axis_column)
                    )
                    graph_config.series[index].y_function = (
                        graph_config.series[index].y_function
                        or _get_column_xpath_template(new_mobile_ucr_restore).format(column.column_id)
                    )
                yield Field(
                    header=Header(text=Text()),
                    template=GraphTemplate.build('graph', graph_config,
                                                 locale_config=_locale_config,
                                                 locale_series_config=_locale_series_config,
                                                 locale_annotation=_locale_annotation)
                )

    def _get_last_sync(report_config):
        if new_mobile_ucr_restore:
            last_sync_string = "format-date(date(instance('commcare-reports:{}')/@last_sync), '%Y-%m-%d %H:%M')"
            last_sync_string = last_sync_string.format(report_config.instance_id)
        else:
            last_sync_string = "format-date(date(instance('reports')/reports/@last_sync), '%Y-%m-%d %H:%M')"

        return Text(
            xpath=Xpath(
                function=last_sync_string
            )
        )

    def _get_description_text(report_config):
        if report_config.use_xpath_description:
            return Text(
                xpath=Xpath(function=config.xpath_description)
            )
        else:
            return Text(
                locale=Locale(id=id_strings.report_description(report_config.uuid))
            )

    detail_id = 'reports.{}.summary'.format(config.uuid)
    detail = Detail(
        title=Text(
            locale=Locale(id=id_strings.report_menu()),
        ),
        fields=[
            Field(
                header=Header(
                    text=Text(
                        locale=Locale(id=id_strings.report_name_header())
                    )
                ),
                template=Template(
                    text=Text(
                        locale=Locale(id=id_strings.report_name(config.uuid))
                    )
                ),
            ),
            Field(
                header=Header(
                    text=Text(
                        locale=Locale(id=id_strings.report_description_header()),
                    )
                ),
                template=Template(
                    text=_get_description_text(config)
                ),
            ),
        ] + [
            Field(
                header=Header(
                    text=Text(
                        locale=Locale(id=id_strings.report_last_sync())
                    )
                ),
                template=Template(text=_get_last_sync(config))
            ),
        ] + list(_get_graph_fields()),
    )
    if config.show_data_table:
        return models.Detail(custom_xml=Detail(
            id=detail_id,
            title=Text(
                locale=Locale(id=id_strings.report_menu()),
            ),
            details=[detail, _get_data_detail(config, domain, new_mobile_ucr_restore)]
        ).serialize().decode('utf-8'))
    else:
        detail.id = detail_id
        return models.Detail(custom_xml=detail.serialize().decode('utf-8'))


def _get_data_detail(config, domain, new_mobile_ucr_restore):
    """
    Adds a data table to the report
    """
    def _column_to_field(column):
        def _get_xpath(col):
            def _get_conditional(condition, if_true, if_false):
                return 'if({condition}, {if_true}, {if_false})'.format(
                    condition=condition,
                    if_true=if_true,
                    if_false=if_false,
                )

            def _get_word_eval(word_translations, default_value):
                word_eval = default_value
                for lang, translation in word_translations.items():
                    word_eval = _get_conditional(
                        "$lang = '{lang}'".format(
                            lang=lang,
                        ),
                        "'{translation}'".format(
                            translation=translation.replace("'", "''"),
                        ),
                        word_eval
                    )
                return word_eval

            try:
                transform = col['transform']
            except KeyError:
                transform = {}

            if transform.get('type') == 'translation':
                if new_mobile_ucr_restore:
                    default_val = "{column_id}"
                else:
                    default_val = "column[@id='{column_id}']"
                xpath_function = default_val
                for word, translations in transform['translations'].items():
                    if isinstance(translations, six.string_types):
                        soft_assert_type_text(translations)
                        # This is a flat mapping, not per-language translations
                        word_eval = "'{}'".format(translations)
                    else:
                        word_eval = _get_word_eval(translations, default_val)
                    xpath_function = _get_conditional(
                        "{value} = '{word}'".format(
                            value=default_val,
                            word=word,
                        ),
                        word_eval,
                        xpath_function
                    )
                return Xpath(
                    function=xpath_function.format(
                        column_id=col.column_id
                    ),
                    variables=[XpathVariable(name='lang', locale_id='lang.current')],
                )
            else:
                if new_mobile_ucr_restore:
                    return Xpath(
                        function="{}".format(col.column_id),
                    )
                else:
                    return Xpath(
                        function="column[@id='{}']".format(col.column_id),
                    )

        return Field(
            header=Header(
                text=Text(
                    locale=Locale(
                        id=id_strings.report_column_header(config.uuid, column.column_id)
                    ),
                )
            ),
            template=Template(
                text=Text(
                    xpath=_get_xpath(column),
                )
            ),
        )

    nodeset_string = 'row{}' if new_mobile_ucr_restore else 'rows/row{}'
    return Detail(
        id='reports.{}.data'.format(config.uuid),
        nodeset=(
            nodeset_string.format(
                MobileSelectFilterHelpers.get_data_filter_xpath(config, domain, new_mobile_ucr_restore))
        ),
        title=Text(
            locale=Locale(id=id_strings.report_data_table()),
        ),
        fields=[
            _column_to_field(c) for c in config.report(domain).report_columns
            if c.type != 'expanded' and c.visible
        ]
    )


class MobileSelectFilterHelpers(object):

    @staticmethod
    def get_options_nodeset(config, filter_slug, new_mobile_ucr_restore=False):
        if new_mobile_ucr_restore:
            instance = "instance('commcare-reports-filters:{report_id}')"
        else:
            instance = "instance('reports')/reports/report[@id='{report_id}']"

        nodeset = instance + "/filters/filter[@field='{filter_slug}']/option"
        return nodeset.format(report_id=config.instance_id, filter_slug=filter_slug)

    @staticmethod
    def get_filters(config, domain):
        return [(slug, f) for slug, f in config.filters.items()
                if isinstance(f, MobileSelectFilter)
                and is_valid_mobile_select_filter_type(config.report(domain).get_ui_filter(slug))]

    @staticmethod
    def get_datum_id(config, filter_slug):
        return 'report_filter_{report_id}_{column_id}'.format(
            report_id=config.uuid, column_id=filter_slug)

    @staticmethod
    def get_select_detail_id(config, filter_slug):
        return "reports.{report_id}.filter.{filter_slug}".format(
            report_id=config.uuid, filter_slug=filter_slug)

    @staticmethod
    def get_select_details(config, filter_slug, domain):
        detail = Detail(
            id=MobileSelectFilterHelpers.get_select_detail_id(config, filter_slug),
            title=Text(config.report(domain).get_ui_filter(filter_slug).label),
            fields=[
                Field(
                    header=Header(
                        text=Text(config.report(domain).get_ui_filter(filter_slug).label)
                    ),
                    template=Template(
                        text=Text(xpath_function='.')
                    ),
                )
            ]
        ).serialize()
        return models.Detail(custom_xml=detail.decode('utf-8'))

    @staticmethod
    def get_data_filter_xpath(config, domain, new_mobile_ucr_restore):
        if new_mobile_ucr_restore:
            base_xpath = "[{column_id}=instance('commcaresession')/session/data/{datum_id}]"
        else:
            base_xpath = "[column[@id='{column_id}']=instance('commcaresession')/session/data/{datum_id}]"

        return ''.join([
            base_xpath.format(
                column_id=config.report(domain).get_ui_filter(slug).field,
                datum_id=MobileSelectFilterHelpers.get_datum_id(config, slug))
            for slug, f in MobileSelectFilterHelpers.get_filters(config, domain)])


def is_valid_mobile_select_filter_type(ui_filter):
    return isinstance(ui_filter, DynamicChoiceListFilter) or isinstance(ui_filter, ChoiceListFilter)


def get_uuids_by_instance_id(app):
    """
    map ReportAppConfig.uuids list to user-defined ReportAppConfig.instance_ids

    This is per-domain, since registering instances (like
    commcare_reports_fixture_instances) is per-domain
    """
    config_ids = defaultdict(list)
    if app.mobile_ucr_restore_version in (MOBILE_UCR_MIGRATING_TO_2, MOBILE_UCR_VERSION_2):
        for module in app.modules:
            if module.module_type == 'report':
                for report_config in module.report_configs:
                    config_ids[report_config.instance_id].append(report_config.uuid)
    return config_ids
