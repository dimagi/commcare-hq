


def get_source_type_from_report_config(report_config):
    """
    Get a report builder source type from an existing ReportConfiguration object
    :param report_config:
    :return:
    """

    return {
        "CommCareCase": "case",
        "XFormInstance": "form"
    }[report_config.config.referenced_doc_type]


