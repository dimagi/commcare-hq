from django.utils.translation import ugettext_lazy as _

LOOKUP_TABLES = 'lookup_tables'
API_ACCESS = 'api_access'

CLOUDCARE = 'cloudcare'

ACTIVE_DATA_MANAGEMENT = 'active_data_management'
CUSTOM_BRANDING = 'custom_branding'

CROSS_PROJECT_REPORTS = 'cross_project_reports'
CUSTOM_REPORTS = 'custom_reports'
REPORT_BUILDER = 'user_configurable_report_builder'

ROLE_BASED_ACCESS = 'role_based_access'

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

USER_CASE = 'user_case'
DATA_CLEANUP = 'data_cleanup'  # bulk archive cases, edit submissions, etc.

MAX_PRIVILEGES = [
    LOOKUP_TABLES,
    API_ACCESS,
    CLOUDCARE,
    ACTIVE_DATA_MANAGEMENT,
    CUSTOM_BRANDING,
    CROSS_PROJECT_REPORTS,
    CUSTOM_REPORTS,
    ROLE_BASED_ACCESS,
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
    USER_CASE,
    DATA_CLEANUP,
]

# These are special privileges related to their own rates in a SoftwarePlanVersion
MOBILE_WORKER_CREATION = 'mobile_worker_creation'

# Other privileges related specifically to accounting processes
ACCOUNTING_ADMIN = 'accounting_admin'
OPERATIONS_TEAM = 'dimagi_ops'


class Titles(object):

    @classmethod
    def get_name_from_privilege(cls, privilege):
        return {
            LOOKUP_TABLES: _("Lookup Tables"),
            API_ACCESS: _("API Access"),
            CLOUDCARE: _("Web-Based Apps (CloudCare)"),
            ACTIVE_DATA_MANAGEMENT: _("Active Data Management"),
            CUSTOM_BRANDING: _("Custom Branding"),
            CROSS_PROJECT_REPORTS: _("Cross-Project Reports"),
            ROLE_BASED_ACCESS: _("Advanced Role-Based Access"),
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
            REPORT_BUILDER: _('User Configurable Report Builder')
        }.get(privilege, privilege)
