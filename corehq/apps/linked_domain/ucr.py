from collections import namedtuple

from corehq.apps.linked_domain.remote_accessors import get_ucr_config as remote_get_ucr_config
from corehq.apps.userreports.dbaccessors import get_datasources_for_domain, get_report_configs_for_domain
from corehq.apps.userreports.models import (
    DataSourceConfiguration,
    ReportConfiguration,
)
from corehq.apps.userreports.tasks import rebuild_indicators

LinkedUCRInfo = namedtuple("LinkedUCRInfo", "datasource report")


def create_linked_ucr(domain_link, report_config_id):
    if domain_link.is_remote:
        remote_configs = remote_get_ucr_config(domain_link, report_config_id)
        datasource = remote_configs["datasource"]
        report_config = remote_configs["report"]
    else:
        report_config = ReportConfiguration.get(report_config_id)
        datasource = DataSourceConfiguration.get(report_config.config_id)
    new_datasource = _get_or_create_datasource_link(domain_link, datasource)
    new_report = _get_or_create_report_link(domain_link, report_config, new_datasource)
    return LinkedUCRInfo(datasource=new_datasource, report=new_report)


def _get_or_create_datasource_link(domain_link, datasource):
    domain_datsources = get_datasources_for_domain(domain_link.linked_domain)
    existing_linked_datasources = [d for d in domain_datsources if d.meta.master_id == datasource.get_id]
    if existing_linked_datasources:
        return existing_linked_datasources[0]

    datasource_json = datasource.to_json()
    datasource_json["domain"] = domain_link.linked_domain
    datasource_json["_id"] = None
    datasource_json["_rev"] = None

    # app_id is needed to edit a report in report builder, but linked
    # reports can't be edited, so we can ignore this
    datasource_json["meta"]["build"]["app_id"] = None

    datasource_json["meta"]["master_id"] = datasource.get_id

    new_datasource = DataSourceConfiguration.wrap(datasource_json)
    new_datasource.save()

    rebuild_indicators.delay(new_datasource.get_id, f"Datasource link: {new_datasource.get_id}")

    return new_datasource


def _get_or_create_report_link(domain_link, report, datasource):
    domain_reports = get_report_configs_for_domain(domain_link.linked_domain)
    existing_linked_reports = [r for r in domain_reports if r.report_meta.master_id == report.get_id]
    if existing_linked_reports:
        return existing_linked_reports[0]

    report_json = report.to_json()
    report_json["report_meta"]["master_id"] = report.get_id
    report_json["domain"] = domain_link.linked_domain
    report_json["config_id"] = datasource.get_id
    report_json["_id"] = None
    report_json["_rev"] = None

    new_report = ReportConfiguration.wrap(report_json)
    new_report.save()

    return new_report


def update_linked_ucr(domain_link, report_id):
    linked_report = ReportConfiguration.get(report_id)

    if domain_link.is_remote:
        remote_configs = remote_get_ucr_config(domain_link, report_id)
        master_report = remote_configs["report"]
        master_datasource = remote_configs["datasource"]
    else:
        master_report = ReportConfiguration.get(linked_report.report_meta.master_id)
        master_datasource = master_report.config

    master_datasource_json = master_datasource.to_json()
    linked_datasource_json = linked_report.config.to_json()

    master_datasource_json["domain"] = domain_link.linked_domain
    master_datasource_json["_id"] = linked_report.config_id
    master_datasource_json["_rev"] = linked_datasource_json["_rev"]
    master_datasource_json["meta"]["master_id"] = linked_datasource_json["meta"]["master_id"]

    linked_datasource_json.update(master_datasource_json)
    DataSourceConfiguration.wrap(linked_datasource_json).save()

    master_report_json = master_report.to_json()
    linked_report_json = linked_report.to_json()

    master_report_json["_id"] = linked_report.get_id
    master_report_json["domain"] = linked_report.domain
    master_report_json["config_id"] = linked_report.config_id
    master_report_json["_rev"] = linked_report_json["_rev"]
    master_report_json["report_meta"]["master_id"] = linked_report_json["report_meta"]["master_id"]

    linked_report_json.update(master_report_json)
    ReportConfiguration.wrap(linked_report_json).save()

    rebuild_indicators.delay(linked_report.config_id, f"Datasource link: {linked_report.config.get_id}")
