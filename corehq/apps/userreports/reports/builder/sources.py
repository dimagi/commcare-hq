from corehq.apps.userreports.app_manager.data_source_meta import DATA_SOURCE_TYPE_CASE, DATA_SOURCE_TYPE_FORM


def get_source_type_from_report_config(report_config):
    """
    Get a report builder source type from an existing ReportConfiguration object
    :param report_config:
    :return:
    """
    return report_config.report_meta.builder_source_type or {
        "CommCareCase": DATA_SOURCE_TYPE_CASE,
        "XFormInstance": DATA_SOURCE_TYPE_FORM,
    }[report_config.config.referenced_doc_type]
