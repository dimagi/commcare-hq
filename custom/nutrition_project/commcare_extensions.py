from corehq.apps.userreports.extension_points import (
    static_ucr_data_source_paths,
    static_ucr_report_paths,
)


@static_ucr_data_source_paths.extend()
def ucr_data_sources():
    return [
        "custom/nutrition_project/ucr/data_sources/*.json",
    ]


@static_ucr_report_paths.extend()
def ucr_reports():
    return [
        "custom/nutrition_project/ucr/reports/*.json",
    ]
