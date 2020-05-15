from collections import namedtuple

from corehq.apps.linked_domain.models import (
    LinkedReportIDMap,
    LinkedReportTypes,
)
from corehq.apps.linked_domain.remote_accessors import (
    get_ucr_config as remote_get_ucr_config,
)
from corehq.apps.userreports.models import (
    DataSourceConfiguration,
    ReportConfiguration,
)

LinkedUCRInfo = namedtuple("LinkedUCRInfo", "datasource_info report_info")


def create_ucr_link(domain_link, report_config):
    if domain_link.is_remote:
        remote_configs = remote_get_ucr_config(domain_link, report_config.get_id)
        datasource = remote_configs['datasource']
        report_config = remote_configs['report']
    else:
        datasource = DataSourceConfiguration.get(report_config.config_id)
    datasource_info = _get_or_create_datasource_link(domain_link, datasource)
    report_info = _get_or_create_report_link(domain_link, report_config, datasource_info)
    return LinkedUCRInfo(datasource_info=datasource_info, report_info=report_info)


def _get_or_create_datasource_link(domain_link, datasource):
    try:
        link_info = LinkedReportIDMap.objects.get(
            linked_domain=domain_link.linked_domain,
            master_id=datasource.get_id,
            model_type=LinkedReportTypes.DATASOURCE,
        )
        return link_info
    except LinkedReportIDMap.DoesNotExist:
        datasource_json = datasource.to_json()
        datasource_json["domain"] = domain_link.linked_domain
        datasource_json["_id"] = None
        datasource_json["_rev"] = None

        # app_id is needed to edit a report in report builder, but linked
        # reports can't be edited, so we can ignore this
        datasource_json["meta"]["build"]["app_id"] = None

        new_datasource = DataSourceConfiguration.wrap(datasource_json)
        new_datasource.save()

        link_info = LinkedReportIDMap(
            linked_domain=domain_link.linked_domain,
            master_domain=domain_link.master_domain,
            master_id=datasource.get_id,
            linked_id=new_datasource.get_id,
            model_type=LinkedReportTypes.DATASOURCE,
        )
        link_info.save()
        return link_info


def _get_or_create_report_link(domain_link, report, datasource_info):
    try:
        link_info = LinkedReportIDMap.objects.get(
            linked_domain=domain_link.linked_domain,
            master_id=report.get_id,
            model_type=LinkedReportTypes.REPORT,
        )
        return link_info
    except LinkedReportIDMap.DoesNotExist:
        report_json = report.to_json()
        report_json["domain"] = domain_link.linked_domain
        report_json["_id"] = None
        report_json["_rev"] = None

        new_report = ReportConfiguration.wrap(report_json)
        new_report.save()

        link_info = LinkedReportIDMap(
            linked_domain=domain_link.linked_domain,
            master_domain=domain_link.master_domain,
            master_id=report.get_id,
            linked_id=new_report.get_id,
            model_type=LinkedReportTypes.REPORT,
        )
        link_info.save()
        return link_info
