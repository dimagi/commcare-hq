from corehq import privileges

paused_v0 = []

# COMMUNITY PLANS

community_v0 = [
    privileges.PROJECT_ACCESS,
    privileges.CASE_SHARING_GROUPS,
    privileges.CHILD_CASES,
    privileges.EXCEL_DASHBOARD,
    privileges.DAILY_SAVED_EXPORT,
]

community_v1 = [
    privileges.PROJECT_ACCESS,
    privileges.CASE_SHARING_GROUPS,
    privileges.CHILD_CASES,
]

# V2 created in December 2019
community_v2 = [
    privileges.PROJECT_ACCESS,
]


# STANDARD PLANS

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

# V1 created in December 2019
standard_v1 = community_v2 + [
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


# PRO PLANS

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

# V1 created in December 2019
pro_v1 = standard_v1 + [
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


# ADVANCED PLANS

advanced_v0 = pro_v0 + [
    privileges.CUSTOM_BRANDING,
    privileges.ACTIVE_DATA_MANAGEMENT,
    privileges.COMMCARE_LOGO_UPLOADER,
    privileges.CUSTOM_INTENTS,
    privileges.ADVANCED_DOMAIN_SECURITY,
    privileges.BUILD_PROFILES,
    privileges.ODATA_FEED,
]

enterprise_v0 = advanced_v0 + []
