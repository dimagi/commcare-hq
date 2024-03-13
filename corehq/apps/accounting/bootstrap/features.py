"""
These are the feature allocations for all tiers of our Software Plan Editions
available for self-service.
"""
from corehq import privileges

paused_v0 = []

# COMMUNITY PLANS

# Grandfathered Community Plans created prior to August 2018
community_v0 = [
    privileges.PROJECT_ACCESS,
    privileges.EXCEL_DASHBOARD,
    privileges.DAILY_SAVED_EXPORT,
    privileges.CASE_SHARING_GROUPS,
    privileges.CHILD_CASES,
    privileges.DATA_FORWARDING,
]

# Grandfathered Community Plans created prior to Dec 18, 2019
community_v1 = [
    privileges.PROJECT_ACCESS,
    privileges.CASE_SHARING_GROUPS,
    privileges.CHILD_CASES,
    privileges.DATA_FORWARDING,
]

# Current Community Plan
community_v2 = [
    privileges.PROJECT_ACCESS,
    privileges.LOGIN_AS,
]


# STANDARD PLANS

# Grandfathered Standard Plans created prior to Dec 18, 2019
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
    privileges.USERCASE,
    privileges.ZAPIER_INTEGRATION,
    privileges.LOGIN_AS,
    privileges.PRACTICE_MOBILE_WORKERS,
]

# Current Standard Plan
standard_v1 = community_v2 + [
    privileges.LOOKUP_TABLES,
    privileges.ROLE_BASED_ACCESS,
    privileges.OUTBOUND_SMS,
    privileges.REMINDERS_FRAMEWORK,
    privileges.CUSTOM_SMS_GATEWAY,
    privileges.BULK_CASE_MANAGEMENT,
    privileges.BULK_USER_MANAGEMENT,
    privileges.ALLOW_EXCESS_USERS,
    privileges.USERCASE,
    privileges.EXCEL_DASHBOARD,
    privileges.DAILY_SAVED_EXPORT,
    privileges.ZAPIER_INTEGRATION,
    privileges.PRACTICE_MOBILE_WORKERS,
    privileges.FORM_LINK_WORKFLOW,
    privileges.PHONE_APK_HEARTBEAT,
    privileges.FORM_CASE_IDS_CASE_IMPORTER,
    privileges.EXPORT_MULTISORT,
]


# PRO PLANS

# Grandfathered Pro Plans created prior to Dec 18, 2019
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

# Current Pro Plan
pro_v1 = standard_v1 + [
    privileges.DATA_FORWARDING,
    privileges.API_ACCESS,
    privileges.CUSTOM_REPORTS,
    privileges.REPORT_BUILDER,
    privileges.REPORT_BUILDER_5,
    privileges.DATA_CLEANUP,
    privileges.TEMPLATED_INTENTS,
    privileges.CASE_SHARING_GROUPS,
    privileges.CHILD_CASES,
    privileges.LITE_RELEASE_MANAGEMENT,
    privileges.LOADTEST_USERS,
    privileges.DATA_FILE_DOWNLOAD,
    privileges.ATTENDANCE_TRACKING,
    privileges.REGEX_FIELD_VALIDATION,
    privileges.EXPORT_OWNERSHIP,
    privileges.CASE_LIST_EXPLORER,
    privileges.CASE_DEDUPE,
]


# ADVANCED PLANS

# Current Advanced Plan
advanced_v0 = pro_v1 + [
    privileges.CLOUDCARE,
    privileges.ACTIVE_DATA_MANAGEMENT,
    privileges.CUSTOM_BRANDING,
    privileges.RESTRICT_ACCESS_BY_LOCATION,
    privileges.INBOUND_SMS,
    privileges.DEIDENTIFIED_DATA,
    privileges.HIPAA_COMPLIANCE_ASSURANCE,
    privileges.COMMCARE_LOGO_UPLOADER,
    privileges.LOCATIONS,
    privileges.CUSTOM_INTENTS,
    privileges.BUILD_PROFILES,
    privileges.ADVANCED_DOMAIN_SECURITY,
    privileges.ODATA_FEED,
    privileges.APP_USER_PROFILES,
    privileges.VIEW_APP_DIFF,
    privileges.LOCATION_SAFE_CASE_IMPORTS,
    privileges.FILTERED_BULK_USER_DOWNLOAD,
    privileges.DATA_DICTIONARY,
    privileges.CASE_COPY,
    privileges.CUSTOM_DOMAIN_ALERTS,
]

enterprise_v0 = advanced_v0 + [
    privileges.GEOCODER,
    privileges.DEFAULT_EXPORT_SETTINGS,
    privileges.RELEASE_MANAGEMENT,
    privileges.APPLICATION_ERROR_REPORT,
]
