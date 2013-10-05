from dimagi.utils.couch.cache.cache_core import DocGenCache


class DomainGenerationCache(DocGenCache):
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
        "domain/by_status",
        "domain/by_organization",
        "hqbilling/domains_marked_for_billing",
    ]

class UserGenerationCache(DocGenCache):
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
        "migration/user_id_by_username",
        "eula_reports/non_eulized_users"
    ]


class GroupGenerationCache(DocGenCache):
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


class UserRoleGenerationCache(DocGenCache):
    generation_key = '#gen#user_role#'
    doc_types = ['UserRole']
    views = [
        'domain/related_to_domain',
        'users/roles_by_domain'
    ]


class OrganizationGenerationCache(DocGenCache):
    generation_key = '#gen#org#'
    doc_types = ['Organization']
    views = [
        'orgs/by_name'
    ]


class TeamGenerationCache(DocGenCache):
    generation_key = '#gen#team#'
    doc_types = ['Team']
    views = [
        'orgs/team_by_domain',
        'orgs/team_by_org_and_name'
    ]
