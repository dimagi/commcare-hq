from dimagi.utils.couch.cache.cache_core import GenerationCache


class ReportGenerationCache(GenerationCache):
    generation_key = '#gen#reports#'
    doc_types = ['ReportConfig', 'ReportNotification']
    views = [
        "reportconfig/all_notifications",
        'reportconfig/configs_by_domain',
        'reportconfig/notifications_by_config',
        "reportconfig/user_notifications",
    ]


class UserReportsDataSourceCache(GenerationCache):
    generation_key = '#gen#userreports#datasource#'
    doc_types = ['DataSourceConfiguration']
    views = [
        'userreports/active_data_sources',
        'userreports/data_sources_by_build_info',
        'userreports/data_sources_by_last_modified',
        'userreports/report_configs_by_data_source',
        'userreports/report_configs_by_domain',
    ]
