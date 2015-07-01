from dimagi.utils.couch.database import iter_docs


def get_number_of_report_configs_by_data_source(domain, data_source_id):
    """
    Return the number of report configurations that use the given data source.
    """
    from corehq.apps.userreports.models import ReportConfiguration
    return ReportConfiguration.view(
        'userreports/report_configs_by_data_source',
        reduce=True,
        key=[domain, data_source_id]
    ).one()['value']


def get_all_report_configs():
    from corehq.apps.userreports.models import ReportConfiguration
    ids = [res['id'] for res in ReportConfiguration.view(
        'userreports/report_configs_by_domain',
        reduce=False,
        include_docs=False,
    )]
    for result in iter_docs(ReportConfiguration.get_db(), ids):
        yield ReportConfiguration.wrap(result)


def get_report_configs_for_domain(domain):
    from corehq.apps.userreports.models import ReportConfiguration
    return sorted(
        ReportConfiguration.view(
            'userreports/report_configs_by_domain',
            key=domain,
            reduce=False,
            include_docs=True,
        ),
        key=lambda report: report.title,
    )
