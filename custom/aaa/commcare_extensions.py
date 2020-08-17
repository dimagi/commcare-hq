from corehq.apps.userreports.extension_points import (
    custom_ucr_expressions,
    static_ucr_data_source_paths,
    static_ucr_report_paths,
)


@static_ucr_data_source_paths.extend()
def aaa_ucr_data_sources():
    return [
        "custom/aaa/ucr/data_sources/*.json",
    ]


@static_ucr_report_paths.extend()
def aaa_ucr_reports():
    return [
        "custom/aaa/ucr/reports/*.json",
    ]


@custom_ucr_expressions.extend()
def aaa_ucr_expressions():
    return [
        ('aaa_awc_owner_id', 'custom.aaa.ucr.expressions.awc_owner_id'),
    ]
