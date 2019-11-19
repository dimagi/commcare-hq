from corehq import privileges

paused_v0 = []

BASIC_ACCESS = [
    privileges.PROJECT_ACCESS,
]

community_v2 = BASIC_ACCESS + []

community_v1 = BASIC_ACCESS + [
    privileges.CASE_SHARING_GROUPS,
    privileges.CHILD_CASES,
]

community_v0 = BASIC_ACCESS + [
    privileges.CASE_SHARING_GROUPS,
    privileges.CHILD_CASES,
    privileges.EXCEL_DASHBOARD,
    privileges.DAILY_SAVED_EXPORT,
]

standard_v0 = community_v0 + [
    privileges.API_ACCESS,
    privileges.LOOKUP_TABLES,
    privileges.OUTBOUND_SMS,
    privileges.REMINDERS_FRAMEWORK,
    privileges.CUSTOM_SMS_GATEWAY,
    privileges.ROLE_BASED_ACCESS,
    privileges.BULK_USER_MANAGEMENT,
    privileges.BULK_CASE_MANAGEMENT,
    privileges.ALLOW_EXCESS_USERS,
    privileges.LOCATIONS,
    privileges.USER_CASE,
    privileges.ZAPIER_INTEGRATION,
    privileges.LOGIN_AS,
    privileges.PRACTICE_MOBILE_WORKERS,
]

pro_v0 = standard_v0 + [
    privileges.CLOUDCARE,
    privileges.CUSTOM_REPORTS,
    privileges.INBOUND_SMS,
    privileges.HIPAA_COMPLIANCE_ASSURANCE,
    privileges.DEIDENTIFIED_DATA,
    privileges.REPORT_BUILDER,
    privileges.DATA_CLEANUP,
    privileges.TEMPLATED_INTENTS,
    privileges.RESTRICT_ACCESS_BY_LOCATION,
    privileges.REPORT_BUILDER_5,
]

pro_v1 = standard_v0 + [
    privileges.CUSTOM_REPORTS,
    privileges.HIPAA_COMPLIANCE_ASSURANCE,
    privileges.DEIDENTIFIED_DATA,
    privileges.REPORT_BUILDER,
    privileges.DATA_CLEANUP,
    privileges.TEMPLATED_INTENTS,
    privileges.RESTRICT_ACCESS_BY_LOCATION,
    privileges.REPORT_BUILDER_5,
]

advanced_v0 = pro_v1 + [
    privileges.INBOUND_SMS,
    privileges.CLOUDCARE,
    privileges.CUSTOM_BRANDING,
    privileges.ACTIVE_DATA_MANAGEMENT,
    privileges.COMMCARE_LOGO_UPLOADER,
    privileges.CUSTOM_INTENTS,
    privileges.ADVANCED_DOMAIN_SECURITY,
    privileges.BUILD_PROFILES,
    privileges.ODATA_FEED,
]

enterprise_v0 = advanced_v0 + []
