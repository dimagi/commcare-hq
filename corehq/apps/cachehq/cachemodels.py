from dimagi.utils.couch.cache.cache_core import GenerationCache


class DomainGenerationCache(GenerationCache):
    generation_key = '#gen#domain#'
    doc_types = ['Domain']
    views = [
        "domain/snapshots",
        "domain/published_snapshots",
        "domain/not_snapshots",
        "domain/copied_from_snapshot",
        "domain/with_deployment",
        "domain/domains",
        "domain/fields_by_prefix",
        "domain/by_organization",
    ]

class UserGenerationCache(GenerationCache):
    generation_key = '#gen#couch_user#'
    doc_types = ['CommCareUser', 'CouchUser', 'WebUser']
    views = [
        "sms/phones_to_domains",
        "hqadmin/users_over_time",
        "hqadmin/emails",
        "users/by_domain",
        "users/phone_users_by_domain",
        "users/web_users_by_domain",
        "users/by_default_phone",
        "users/admins_by_domain",
        "users/by_org_and_team",
        "users/by_username",
        "users/mailing_list_emails",
        "domain/related_to_domain",
        "domain/old_users",
        "domain/docs",
        "sms/phones_to_domains",
        "eula_reports/non_eulized_users"
    ]


class GroupGenerationCache(GenerationCache):
    generation_key = '#gen#group#'
    doc_types = ['Group']
    views = [
        "groups/by_user",
        "groups/by_hierarchy_type",
        "groups/by_user_type",
        "groups/by_name",
        "groups/all_groups",
        "groups/by_domain",
        "users/by_group",
    ]


class UserRoleGenerationCache(GenerationCache):
    generation_key = '#gen#user_role#'
    doc_types = ['UserRole']
    views = [
        'domain/related_to_domain',
        'users/roles_by_domain'
    ]


class OrganizationGenerationCache(GenerationCache):
    generation_key = '#gen#org#'
    doc_types = ['Organization']
    views = [
        'orgs/by_name'
    ]


class TeamGenerationCache(GenerationCache):
    generation_key = '#gen#team#'
    doc_types = ['Team']
    views = [
        'orgs/team_by_domain',
        'orgs/team_by_org_and_name'
    ]

class ReportGenerationCache(GenerationCache):
    generation_key = '#gen#reports#'
    doc_types = ['ReportConfig', 'HQGroupExportConfiguration', 'ReportNotification']
    views = [
        'reportconfig/configs_by_domain',
        'reportconfig/notifications_by_config',
        "reportconfig/user_notifications",
        "reportconfig/daily_notifications",
        'groupexport/by_domain',
    ]


class DefaultConsumptionGenerationCache(GenerationCache):
    generation_key = '#gen#default_consumption#'
    doc_types = ['DefaultConsumption']
    views = [
        'consumption/consumption_index',
    ]


class LocationGenerationCache(GenerationCache):
    generation_key = '#gen#location#'
    doc_types = ['Location']
    views = [
        'commtrack/locations_by_code',
        '_all_docs',
    ]


class DomainInvitationGenerationCache(GenerationCache):
    generation_key = '#gen#invitation#'
    doc_types = ['Invitation']
    views = [
        'users/open_invitations_by_email',
        'users/open_invitations_by_domain',
    ]


class CommtrackConfigGenerationCache(GenerationCache):
    generation_key = '#gen#commtrackconfig#'
    doc_types = ['CommtrackConfig']
    views = [
        'commtrack/domain_config',
    ]


class UserReportsDataSourceCache(GenerationCache):
    generation_key = '#gen#userreports#datasource#'
    doc_types = ['DataSourceConfiguration']
    views = [
        'userreports/data_sources_by_build_info',
    ]


class UserReportsReportConfigCache(GenerationCache):
    generation_key = '#gen#userreports#reportconfig#'
    doc_types = ['ReportConfiguration']
    views = [
        'userreports/report_configs_by_domain',
    ]
