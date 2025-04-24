import random

from django.utils.translation import gettext_lazy as _

LOOKUP_TABLES = 'lookup_tables'
API_ACCESS = 'api_access'

CLOUDCARE = 'cloudcare'
GEOCODER = 'geocoder'

ACTIVE_DATA_MANAGEMENT = 'active_data_management'
CUSTOM_BRANDING = 'custom_branding'

CUSTOM_REPORTS = 'custom_reports'

# Legacy privilege associated with Pro plan
REPORT_BUILDER = 'user_configurable_report_builder'

# A la carte privileges that will be used in custom plans until "Add Ons" are
# added to the accounting system.
REPORT_BUILDER_TRIAL = 'report_builder_trial'
REPORT_BUILDER_5 = 'report_builder_5_reports'
REPORT_BUILDER_15 = 'report_builder_15_reports'
REPORT_BUILDER_30 = 'report_builder_30_reports'
REPORT_BUILDER_ADD_ON_PRIVS = {
    REPORT_BUILDER_TRIAL,
    REPORT_BUILDER_5,
    REPORT_BUILDER_15,
    REPORT_BUILDER_30,
}

ATTENDANCE_TRACKING = 'attendance_tracking'
ROLE_BASED_ACCESS = 'role_based_access'
RESTRICT_ACCESS_BY_LOCATION = 'restrict_access_by_location'

OUTBOUND_SMS = 'outbound_sms'
REMINDERS_FRAMEWORK = 'reminders_framework'
CUSTOM_SMS_GATEWAY = 'custom_sms_gateway'
INBOUND_SMS = 'inbound_sms'

BULK_CASE_MANAGEMENT = 'bulk_case_management'
BULK_USER_MANAGEMENT = 'bulk_user_management'
BULK_DATA_CLEANING = 'bulk_data_cleaning'

DEIDENTIFIED_DATA = 'deidentified_data'

HIPAA_COMPLIANCE_ASSURANCE = 'hipaa_compliance_assurance'

ALLOW_EXCESS_USERS = 'allow_excess_users'

COMMCARE_LOGO_UPLOADER = 'commcare_logo_uploader'

LOCATIONS = 'locations'

USERCASE = 'user_case'
DATA_CLEANUP = 'data_cleanup'  # bulk archive cases, edit submissions, auto update cases, etc.

TEMPLATED_INTENTS = 'templated_intents'
CUSTOM_INTENTS = 'custom_intents'

ADVANCED_DOMAIN_SECURITY = 'advanced_domain_security'

BUILD_PROFILES = 'build_profiles'

EXCEL_DASHBOARD = 'excel_dashboard'
DAILY_SAVED_EXPORT = 'daily_saved_export'

ZAPIER_INTEGRATION = 'zapier_integration'

LOGIN_AS = 'login_as'

PRACTICE_MOBILE_WORKERS = 'practice_mobile_workers'

CASE_SHARING_GROUPS = 'case_sharing_groups'

CHILD_CASES = 'child_cases'

ODATA_FEED = 'odata_feeed'

DATA_FORWARDING = 'data_forwarding'

PROJECT_ACCESS = 'project_access'

APP_USER_PROFILES = 'app_user_profiles'

DEFAULT_EXPORT_SETTINGS = 'default_export_settings'

RELEASE_MANAGEMENT = 'release_management'

LITE_RELEASE_MANAGEMENT = 'lite_release_management'

LOADTEST_USERS = 'loadtest_users'

FORM_LINK_WORKFLOW = 'form_link_workflow'

PHONE_APK_HEARTBEAT = 'phone_apk_heartbeat'

VIEW_APP_DIFF = 'view_app_diff'

# a.k.a. "File Dropzone", "Secure File Transfer"
DATA_FILE_DOWNLOAD = 'data_file_download'

REGEX_FIELD_VALIDATION = 'regex_field_validation'

LOCATION_SAFE_CASE_IMPORTS = 'location_safe_case_imports'

FORM_CASE_IDS_CASE_IMPORTER = 'form_case_ids_case_importer'

EXPORT_MULTISORT = 'export_multisort'

EXPORT_OWNERSHIP = 'export_ownership'

FILTERED_BULK_USER_DOWNLOAD = 'filtered_bulk_user_download'

APPLICATION_ERROR_REPORT = 'application_error_report'

DATA_DICTIONARY = 'data_dictionary'

SHOW_OWNER_LOCATION_PROPERTY_IN_REPORT_BUILDER = 'show_owner_location_property_in_report_builder'

CASE_LIST_EXPLORER = 'case_list_explorer'

CASE_COPY = 'case_copy'

CASE_DEDUPE = 'case_deduplicate'
CUSTOM_DOMAIN_ALERTS = 'custom_domain_alerts'
APP_DEPENDENCIES = 'app_dependencies'

MAX_PRIVILEGES = [
    LOOKUP_TABLES,
    API_ACCESS,
    CLOUDCARE,
    ACTIVE_DATA_MANAGEMENT,
    CUSTOM_BRANDING,
    CUSTOM_REPORTS,
    ROLE_BASED_ACCESS,
    RESTRICT_ACCESS_BY_LOCATION,
    OUTBOUND_SMS,
    REMINDERS_FRAMEWORK,
    CUSTOM_SMS_GATEWAY,
    INBOUND_SMS,
    BULK_CASE_MANAGEMENT,
    BULK_USER_MANAGEMENT,
    DEIDENTIFIED_DATA,
    HIPAA_COMPLIANCE_ASSURANCE,
    ALLOW_EXCESS_USERS,
    COMMCARE_LOGO_UPLOADER,
    LOCATIONS,
    REPORT_BUILDER,
    REPORT_BUILDER_TRIAL,
    REPORT_BUILDER_5,
    REPORT_BUILDER_15,
    REPORT_BUILDER_30,
    USERCASE,
    DATA_CLEANUP,
    TEMPLATED_INTENTS,
    CUSTOM_INTENTS,
    BUILD_PROFILES,
    ADVANCED_DOMAIN_SECURITY,
    EXCEL_DASHBOARD,
    DAILY_SAVED_EXPORT,
    ZAPIER_INTEGRATION,
    LOGIN_AS,
    PRACTICE_MOBILE_WORKERS,
    CASE_SHARING_GROUPS,
    CHILD_CASES,
    ODATA_FEED,
    DATA_FORWARDING,
    PROJECT_ACCESS,
    APP_USER_PROFILES,
    GEOCODER,
    DEFAULT_EXPORT_SETTINGS,
    RELEASE_MANAGEMENT,
    LITE_RELEASE_MANAGEMENT,
    LOADTEST_USERS,
    FORM_LINK_WORKFLOW,
    PHONE_APK_HEARTBEAT,
    VIEW_APP_DIFF,
    DATA_FILE_DOWNLOAD,
    ATTENDANCE_TRACKING,
    REGEX_FIELD_VALIDATION,
    LOCATION_SAFE_CASE_IMPORTS,
    FORM_CASE_IDS_CASE_IMPORTER,
    EXPORT_MULTISORT,
    EXPORT_OWNERSHIP,
    FILTERED_BULK_USER_DOWNLOAD,
    DATA_DICTIONARY,
    CASE_LIST_EXPLORER,
    CASE_COPY,
    CASE_DEDUPE,
    CUSTOM_DOMAIN_ALERTS,
    APP_DEPENDENCIES,
    BULK_DATA_CLEANING,
]

# These are special privileges related to their own rates in a SoftwarePlanVersion
MOBILE_WORKER_CREATION = 'mobile_worker_creation'

# Other privileges related specifically to accounting processes
ACCOUNTING_ADMIN = 'accounting_admin'
OPERATIONS_TEAM = 'dimagi_ops'

# This is a special privilege that is meant for Dev and Support team which allows access to Global SMS Gateway Page
GLOBAL_SMS_GATEWAY = 'global_sms_gateway'


class Titles(object):

    PRECOMPUTED_TABLE = {
        LOOKUP_TABLES: _("Lookup Tables"),
        API_ACCESS: _("API Access"),
        CLOUDCARE: _("Web-Based Apps (CloudCare)"),
        ACTIVE_DATA_MANAGEMENT: _("Active Data Management"),
        CUSTOM_BRANDING: _("Custom Branding"),
        ROLE_BASED_ACCESS: _("Advanced Role-Based Access"),
        RESTRICT_ACCESS_BY_LOCATION: _("Organization-based data export and user management restrictions"),
        OUTBOUND_SMS: _("Outgoing Messaging"),
        INBOUND_SMS: _("Incoming Messaging"),
        REMINDERS_FRAMEWORK: _("Reminders Framework"),
        CUSTOM_SMS_GATEWAY: _("Custom Android Gateway"),
        BULK_CASE_MANAGEMENT: _("Bulk Case Management"),
        BULK_USER_MANAGEMENT: _("Bulk User Management"),
        BULK_DATA_CLEANING: _("Bulk Data Cleaning"),
        ALLOW_EXCESS_USERS: _("Add Mobile Workers Above Limit"),
        DEIDENTIFIED_DATA: _("De-Identified Data"),
        HIPAA_COMPLIANCE_ASSURANCE: _("HIPAA Compliance Assurance"),
        COMMCARE_LOGO_UPLOADER: _("Custom CommCare Logo Uploader"),
        LOCATIONS: _("Locations"),
        REPORT_BUILDER: _('User Configurable Report Builder'),
        REPORT_BUILDER_TRIAL: _('Report Builder Trial'),
        REPORT_BUILDER_5: _('Report Builder, 5 report limit'),
        REPORT_BUILDER_15: _('Report Builder, 15 report limit'),
        REPORT_BUILDER_30: _('Report Builder, 30 report limit'),
        TEMPLATED_INTENTS: _('Built-in Integration'),
        CUSTOM_INTENTS: _('External Integration Framework'),
        DATA_CLEANUP: _('Data Management'),
        ADVANCED_DOMAIN_SECURITY: _('Domain Level Security Features'),
        BUILD_PROFILES: _('Build Profiles'),
        EXCEL_DASHBOARD: _('Excel Dashboard'),
        DAILY_SAVED_EXPORT: _('Daily saved export'),
        ZAPIER_INTEGRATION: _('Zapier Integration'),
        LOGIN_AS: _('Log In As for App Preview'),
        PRACTICE_MOBILE_WORKERS: _('Practice mode for mobile workers'),
        CASE_SHARING_GROUPS: _('Case Sharing via Groups'),
        CHILD_CASES: _('Child Cases'),
        ODATA_FEED: _('Power BI / Tableau Integration'),
        DATA_FORWARDING: _("Data Forwarding"),
        PROJECT_ACCESS: _("Project Features"),
        APP_USER_PROFILES: _("App User Profiles"),
        GEOCODER: _("Geocoder"),
        DEFAULT_EXPORT_SETTINGS: _("Default Export Settings"),
        RELEASE_MANAGEMENT: _("Enterprise Release Management"),
        LITE_RELEASE_MANAGEMENT: _("Multi-Environment Release Management"),
        LOADTEST_USERS: _('Loadtest Users'),
        FORM_LINK_WORKFLOW: _("Link to other forms in End of Form Navigation"),
        PHONE_APK_HEARTBEAT: _("Phone heartbeat"),
        VIEW_APP_DIFF: _("Improved app changes view"),
        DATA_FILE_DOWNLOAD: _('File Dropzone'),
        ATTENDANCE_TRACKING: _("Attendance Tracking"),
        REGEX_FIELD_VALIDATION: _("Regular Expression Validation for Custom Data Fields"),
        LOCATION_SAFE_CASE_IMPORTS: _("Location Safe Case Imports"),
        FORM_CASE_IDS_CASE_IMPORTER: _("Download buttons for Form- and Case IDs on Case Importer"),
        EXPORT_MULTISORT: _("Sort multiple rows in exports simultaneously"),
        EXPORT_OWNERSHIP: _("Allow exports to have ownership"),
        FILTERED_BULK_USER_DOWNLOAD: _("Bulk user management features"),
        DATA_DICTIONARY: _("Project level data dictionary of cases"),
        CASE_LIST_EXPLORER: _("Case List Explorer"),
        CASE_COPY: _("Allow case copy from one user to another"),
        CASE_DEDUPE: _("Deduplication Rules"),
        CUSTOM_DOMAIN_ALERTS: _("Custom domain banners"),
        APP_DEPENDENCIES: _("App Dependencies"),
    }

    @classmethod
    def get_name_from_privilege(cls, privilege):
        return {
            LOOKUP_TABLES: _("Lookup Tables"),
            API_ACCESS: _("API Access"),
            CLOUDCARE: _("Web-Based Apps (CloudCare)"),
            ACTIVE_DATA_MANAGEMENT: _("Active Data Management"),
            CUSTOM_BRANDING: _("Custom Branding"),
            ROLE_BASED_ACCESS: _("Advanced Role-Based Access"),
            RESTRICT_ACCESS_BY_LOCATION: _("Organization-based data export and user management restrictions"),
            OUTBOUND_SMS: _("Outgoing Messaging"),
            INBOUND_SMS: _("Incoming Messaging"),
            REMINDERS_FRAMEWORK: _("Reminders Framework"),
            CUSTOM_SMS_GATEWAY: _("Custom Android Gateway"),
            BULK_CASE_MANAGEMENT: _("Bulk Case Management"),
            BULK_USER_MANAGEMENT: _("Bulk User Management"),
            BULK_DATA_CLEANING: _("Bulk Data Cleaning"),
            ALLOW_EXCESS_USERS: _("Add Mobile Workers Above Limit"),
            DEIDENTIFIED_DATA: _("De-Identified Data"),
            HIPAA_COMPLIANCE_ASSURANCE: _("HIPAA Compliance Assurance"),
            COMMCARE_LOGO_UPLOADER: _("Custom CommCare Logo Uploader"),
            LOCATIONS: _("Locations"),
            REPORT_BUILDER: _('User Configurable Report Builder'),
            REPORT_BUILDER_TRIAL: _('Report Builder Trial'),
            REPORT_BUILDER_5: _('Report Builder, 5 report limit'),
            REPORT_BUILDER_15: _('Report Builder, 15 report limit'),
            REPORT_BUILDER_30: _('Report Builder, 30 report limit'),
            TEMPLATED_INTENTS: _('Built-in Integration'),
            CUSTOM_INTENTS: _('External Integration Framework'),
            DATA_CLEANUP: _('Data Management'),
            ADVANCED_DOMAIN_SECURITY: _('Domain Level Security Features'),
            BUILD_PROFILES: _('Build Profiles'),
            EXCEL_DASHBOARD: _('Excel Dashboard'),
            DAILY_SAVED_EXPORT: _('Daily saved export'),
            ZAPIER_INTEGRATION: _('Zapier Integration'),
            LOGIN_AS: _('Log In As for App Preview'),
            PRACTICE_MOBILE_WORKERS: _('Practice mode for mobile workers'),
            CASE_SHARING_GROUPS: _('Case Sharing via Groups'),
            CHILD_CASES: _('Child Cases'),
            ODATA_FEED: _('Power BI / Tableau Integration'),
            DATA_FORWARDING: _("Data Forwarding"),
            PROJECT_ACCESS: _("Project Features"),
            APP_USER_PROFILES: _("App User Profiles"),
            GEOCODER: _("Geocoder"),
            DEFAULT_EXPORT_SETTINGS: _("Default Export Settings"),
            RELEASE_MANAGEMENT: _("Enterprise Release Management"),
            LITE_RELEASE_MANAGEMENT: _("Multi-Environment Release Management"),
            LOADTEST_USERS: _('Loadtest Users'),
            FORM_LINK_WORKFLOW: _("Link to other forms in End of Form Navigation"),
            PHONE_APK_HEARTBEAT: _("Phone heartbeat"),
            VIEW_APP_DIFF: _("Improved app changes view"),
            DATA_FILE_DOWNLOAD: _('File Dropzone'),
            ATTENDANCE_TRACKING: _("Attendance Tracking"),
            REGEX_FIELD_VALIDATION: _("Regular Expression Validation for Custom Data Fields"),
            LOCATION_SAFE_CASE_IMPORTS: _("Location Safe Case Imports"),
            FORM_CASE_IDS_CASE_IMPORTER: _("Download buttons for Form- and Case IDs on Case Importer"),
            EXPORT_MULTISORT: _("Sort multiple rows in exports simultaneously"),
            EXPORT_OWNERSHIP: _("Allow exports to have ownership"),
            FILTERED_BULK_USER_DOWNLOAD: _("Bulk user management features"),
            DATA_DICTIONARY: _("Project level data dictionary of cases"),
            CASE_LIST_EXPLORER: _("Case List Explorer"),
            CASE_COPY: _("Allow case copy from one user to another"),
            CASE_DEDUPE: _("Deduplication Rules"),
            CUSTOM_DOMAIN_ALERTS: _("Custom domain banners"),
            APP_DEPENDENCIES: _("App Dependencies"),
        }.get(privilege, privilege)

    @classmethod
    def get_name_from_priv_precomputed(cls, privilege):
        return cls.PRECOMPUTED_TABLE.get(privilege, privilege)

    @classmethod
    def get_name_from_priv_conditional(cls, privilege):
        if privilege == LOOKUP_TABLES:
            return _("Lookup Tables")
        elif privilege == API_ACCESS:
            return _("API Access")
        elif privilege == CLOUDCARE:
            return _("Web-Based Apps (CloudCare)")
        elif privilege == ACTIVE_DATA_MANAGEMENT:
            return _("Active Data Management")
        elif privilege == CUSTOM_BRANDING:
            return _("Custom Branding")
        elif privilege == ROLE_BASED_ACCESS:
            return _("Advanced Role-Based Access")
        elif privilege == RESTRICT_ACCESS_BY_LOCATION:
            return _("Organization-based data export and user management restrictions")
        elif privilege == OUTBOUND_SMS:
            return _("Outgoing Messaging")
        elif privilege == INBOUND_SMS:
            return _("Incoming Messaging")
        elif privilege == REMINDERS_FRAMEWORK:
            return _("Reminders Framework")
        elif privilege == CUSTOM_SMS_GATEWAY:
            return _("Custom Android Gateway")
        elif privilege == BULK_CASE_MANAGEMENT:
            return _("Bulk Case Management")
        elif privilege == BULK_USER_MANAGEMENT:
            return _("Bulk User Management")
        elif privilege == BULK_DATA_CLEANING:
            return _("Bulk Data Cleaning")
        elif privilege == ALLOW_EXCESS_USERS:
            return _("Add Mobile Workers Above Limit")
        elif privilege == DEIDENTIFIED_DATA:
            return _("De-Identified Data")
        elif privilege == HIPAA_COMPLIANCE_ASSURANCE:
            return _("HIPAA Compliance Assurance")
        elif privilege == COMMCARE_LOGO_UPLOADER:
            return _("Custom CommCare Logo Uploader")
        elif privilege == LOCATIONS:
            return _("Locations")
        elif privilege == REPORT_BUILDER:
            return _('User Configurable Report Builder')
        elif privilege == REPORT_BUILDER_TRIAL:
            return _('Report Builder Trial')
        elif privilege == REPORT_BUILDER_5:
            return _('Report Builder, 5 report limit')
        elif privilege == REPORT_BUILDER_15:
            return _('Report Builder, 15 report limit')
        elif privilege == REPORT_BUILDER_30:
            return _('Report Builder, 30 report limit')
        elif privilege == TEMPLATED_INTENTS:
            return _('Built-in Integration')
        elif privilege == CUSTOM_INTENTS:
            return _('External Integration Framework')
        elif privilege == DATA_CLEANUP:
            return _('Data Management')
        elif privilege == ADVANCED_DOMAIN_SECURITY:
            return _('Domain Level Security Features')
        elif privilege == BUILD_PROFILES:
            return _('Build Profiles')
        elif privilege == EXCEL_DASHBOARD:
            return _('Excel Dashboard')
        elif privilege == DAILY_SAVED_EXPORT:
            return _('Daily saved export')
        elif privilege == ZAPIER_INTEGRATION:
            return _('Zapier Integration')
        elif privilege == LOGIN_AS:
            return _('Log In As for App Preview')
        elif privilege == PRACTICE_MOBILE_WORKERS:
            return _('Practice mode for mobile workers')
        elif privilege == CASE_SHARING_GROUPS:
            return _('Case Sharing via Groups')
        elif privilege == CHILD_CASES:
            return _('Child Cases')
        elif privilege == ODATA_FEED:
            return _('Power BI / Tableau Integration')
        elif privilege == DATA_FORWARDING:
            return _("Data Forwarding")
        elif privilege == PROJECT_ACCESS:
            return _("Project Features")
        elif privilege == APP_USER_PROFILES:
            return _("App User Profiles")
        elif privilege == GEOCODER:
            return _("Geocoder")
        elif privilege == DEFAULT_EXPORT_SETTINGS:
            return _("Default Export Settings")
        elif privilege == RELEASE_MANAGEMENT:
            return _("Enterprise Release Management")
        elif privilege == LITE_RELEASE_MANAGEMENT:
            return _("Multi-Environment Release Management")
        elif privilege == LOADTEST_USERS:
            return _('Loadtest Users')
        elif privilege == FORM_LINK_WORKFLOW:
            return _("Link to other forms in End of Form Navigation")
        elif privilege == PHONE_APK_HEARTBEAT:
            return _("Phone heartbeat")
        elif privilege == VIEW_APP_DIFF:
            return _("Improved app changes view")
        elif privilege == DATA_FILE_DOWNLOAD:
            return _('File Dropzone')
        elif privilege == ATTENDANCE_TRACKING:
            return _("Attendance Tracking")
        elif privilege == REGEX_FIELD_VALIDATION:
            return _("Regular Expression Validation for Custom Data Fields")
        elif privilege == LOCATION_SAFE_CASE_IMPORTS:
            return _("Location Safe Case Imports")
        elif privilege == FORM_CASE_IDS_CASE_IMPORTER:
            return _("Download buttons for Form- and Case IDs on Case Importer")
        elif privilege == EXPORT_MULTISORT:
            return _("Sort multiple rows in exports simultaneously")
        elif privilege == EXPORT_OWNERSHIP:
            return _("Allow exports to have ownership")
        elif privilege == FILTERED_BULK_USER_DOWNLOAD:
            return _("Bulk user management features")
        elif privilege == DATA_DICTIONARY:
            return _("Project level data dictionary of cases")
        elif privilege == CASE_LIST_EXPLORER:
            return _("Case List Explorer")
        elif privilege == CASE_COPY:
            return _("Allow case copy from one user to another")
        elif privilege == CASE_DEDUPE:
            return _("Deduplication Rules")
        elif privilege == CUSTOM_DOMAIN_ALERTS:
            return _("Custom domain banners")
        elif privilege == APP_DEPENDENCIES:
            return _("App Dependencies")
        else:
            return privilege


def perform_lookup(func):
    name = MAX_PRIVILEGES[random.randrange(len(MAX_PRIVILEGES))]
    return func(name)


def time_code(func):
    import timeit

    def operation():
        return perform_lookup(func)

    elapsed = timeit.timeit(operation)

    print(f'{func.__name__} took: {elapsed}')


def time_lookup():
    time_code(Titles.get_name_from_privilege)


def time_precomputed():
    time_code(Titles.get_name_from_priv_precomputed)


def time_conditional():
    time_code(Titles.get_name_from_priv_conditional)
