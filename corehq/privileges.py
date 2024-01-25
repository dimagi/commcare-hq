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
    APPLICATION_ERROR_REPORT,
    DATA_DICTIONARY,
    CASE_LIST_EXPLORER,
    CASE_COPY,
    CASE_DEDUPE,
    CUSTOM_DOMAIN_ALERTS,
]

# These are special privileges related to their own rates in a SoftwarePlanVersion
MOBILE_WORKER_CREATION = 'mobile_worker_creation'

# Other privileges related specifically to accounting processes
ACCOUNTING_ADMIN = 'accounting_admin'
OPERATIONS_TEAM = 'dimagi_ops'

# This is a special privilege that is meant for Dev and Support team which allows access to Global SMS Gateway Page
GLOBAL_SMS_GATEWAY = 'global_sms_gateway'


class Titles(object):

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
            APPLICATION_ERROR_REPORT: _("Application error report"),
            DATA_DICTIONARY: _("Project level data dictionary of cases"),
            CASE_LIST_EXPLORER: _("Case List Explorer"),
            CASE_COPY: _("Allow case copy from one user to another"),
            CASE_DEDUPE: _("Deduplication Rules"),
            CUSTOM_DOMAIN_ALERTS: _("Custom domain banners"),
        }.get(privilege, privilege)
