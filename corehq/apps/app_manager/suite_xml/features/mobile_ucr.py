from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.models import ReportModule, ReportGraphConfig
from corehq.apps.app_manager import models
from corehq.apps.app_manager.suite_xml.xml_models import Locale, Text, Command, Entry, \
    SessionDatum, Detail, Header, Field, Template, Series, ConfigurationGroup, \
    ConfigurationItem, GraphTemplate, Graph, Xpath
from corehq.util.quickcache import quickcache


@quickcache(['report_module.unique_id'])
def _load_reports(report_module):
    if not report_module._loaded:
        # load reports in bulk to avoid hitting the database for each one
        for i, report in enumerate(report_module.reports):
            report_module.report_configs[i]._report = report
    report_module._loaded = True


class ReportModuleSuiteHelper(object):
    def __init__(self, report_module):
        assert isinstance(report_module, ReportModule)
        self.report_module = report_module
        self._loaded = None

    def get_details(self):
        _load_reports(self.report_module)
        for config in self.report_module.report_configs:
            yield (_get_select_detail_id(config), _get_select_details(config), True)
            yield (_get_summary_detail_id(config), _get_summary_details(config), True)

    def get_custom_entries(self):
        _load_reports(self.report_module)
        for config in self.report_module.report_configs:
            yield _get_config_entry(config)


def _get_config_entry(config):
    return Entry(
        command=Command(
            id='reports.{}'.format(config.uuid),
            text=Text(
                locale=Locale(id=id_strings.report_name(config.uuid)),
            ),
        ),
        datums=[
            SessionDatum(
                detail_confirm=_get_summary_detail_id(config),
                detail_select=_get_select_detail_id(config),
                id='report_id_{}'.format(config.uuid),
                nodeset="instance('reports')/reports/report[@id='{}']".format(config.uuid),
                value='./@id',
            ),
        ]
    )


def _get_select_detail_id(config):
    return 'reports.{}.select'.format(config.uuid)


def _get_summary_detail_id(config):
    return 'reports.{}.summary'.format(config.uuid)


def _get_select_details(config):
    return models.Detail(custom_xml=Detail(
        id='reports.{}.select'.format(config.uuid),
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
    ).serialize())


def _get_summary_details(config):
    def _get_graph_fields():
        from corehq.apps.userreports.reports.specs import MultibarChartSpec
        # todo: make this less hard-coded
        for chart_config in config.report.charts:
            if isinstance(chart_config, MultibarChartSpec):
                graph_config = config.graph_configs.get(chart_config.chart_id, ReportGraphConfig())

                def _column_to_series(column):
                    return Series(
                        nodeset="instance('reports')/reports/report[@id='{}']/rows/row".format(config.uuid),
                        x_function="column[@id='{}']".format(chart_config.x_axis_column),
                        y_function="column[@id='{}']".format(column),
                        configuration=ConfigurationGroup(configs=[
                            ConfigurationItem(id=key, xpath_function=value)
                            for key, value in graph_config.series_configs.get(column, {}).items()
                        ])
                    )
                yield Field(
                    header=Header(text=Text()),
                    template=GraphTemplate(
                        form='graph',
                        graph=Graph(
                            type=graph_config.graph_type,
                            series=[_column_to_series(c.column_id) for c in chart_config.y_axis_columns],
                            configuration=ConfigurationGroup(configs=[
                                ConfigurationItem(id=key, xpath_function=value)
                                for key, value in graph_config.config.items()
                            ]),
                        ),
                    )
                )

    return models.Detail(custom_xml=Detail(
        id='reports.{}.summary'.format(config.uuid),
        title=Text(
            locale=Locale(id=id_strings.report_menu()),
        ),
        details=[
            Detail(
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
                            text=Text(
                                xpath=Xpath(function=config.description)
                            )
                        ),
                    ),
                ] + [
                    Field(
                        header=Header(
                            text=Text(
                                locale=Locale(id=id_strings.report_last_sync())
                            )
                        ),
                        template=Template(
                            text=Text(
                                xpath=Xpath(
                                    function="format-date(date(instance('reports')/reports/@last_sync), '%Y-%m-%d %H:%M')"
                                )
                            )
                        )
                    ),
                ] + list(_get_graph_fields()),
            ),
            _get_data_detail(config),
        ],
    ).serialize())


def _get_data_detail(config):
    def _column_to_field(column):
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
                    xpath=Xpath(function="column[@id='{}']".format(column.column_id)))
            ),
        )

    return Detail(
        id='reports.{}.data'.format(config.uuid),
        nodeset='rows/row',
        title=Text(
            locale=Locale(id=id_strings.report_data_table()),
        ),
        fields=[_column_to_field(c) for c in config.report.report_columns]
    )
