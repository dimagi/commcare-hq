from dimagi.utils.couch.cache.cache_core import GenerationCache


class DomainGenerationCache(GenerationCache):
    generation_key = '#gen#domain#'
    doc_types = ['Domain']
    views = [
        "domain/not_snapshots",
        "domain/domains",
    ]


class UserGenerationCache(GenerationCache):
    generation_key = '#gen#couch_user#'
    doc_types = ['CommCareUser', 'CouchUser', 'WebUser']
    views = [
        "users/by_domain",
        "users/phone_users_by_domain",
        "users/by_default_phone",
        "users/by_username",
        "domain/old_users",
    ]


class GroupGenerationCache(GenerationCache):
    generation_key = '#gen#group#'
    doc_types = ['Group']
    views = [
        "groups/by_user",
        "groups/by_name",
        "groups/all_groups",
        "users/by_group",
    ]


class UserRoleGenerationCache(GenerationCache):
    generation_key = '#gen#user_role#'
    doc_types = ['UserRole']
    views = [
        'users/roles_by_domain'
    ]


class ReportGenerationCache(GenerationCache):
    generation_key = '#gen#reports#'
    doc_types = ['ReportConfig', 'ReportNotification']
    views = [
        'reportconfig/configs_by_domain',
        'reportconfig/notifications_by_config',
        "reportconfig/user_notifications",
        "reportconfig/daily_notifications",
    ]


class UserReportsDataSourceCache(GenerationCache):
    generation_key = '#gen#userreports#datasource#'
    doc_types = ['DataSourceConfiguration']
    views = [
        'userreports/data_sources_by_build_info',
    ]
